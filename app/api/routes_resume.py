import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.database import get_resume_repository
from app.core.llm_client import get_llm_client
from app.models.resume_schema import ResumeParseResponse, ResumeProfile, ResumeRephraseRequest, ResumeRephraseResponse
from app.services.document_text_extractor import DocumentTextExtractor
from app.services.resume_image_storage import LocalResumeImageStorage, ResumeImageStorage, S3ResumeImageStorage
from app.services.resume_parser import ResumeParserService, normalize_resume_profile_payload
from app.services.resume_rephraser import ResumeRephraseService
from app.services.resume_repository import ResumeNotFoundError, ResumeRepositoryNotConfiguredError
from app.utils.file_validator import read_and_validate_file
from app.utils.resume_detector import validate_resume_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resumes", tags=["resumes"])
HTTP_422_UNPROCESSABLE_CONTENT = 422


def normalize_user_id(user_id: str | None) -> str | None:
    if user_id is None:
        return None

    normalized = user_id.strip()
    return normalized or None


def get_resume_image_storage(settings: Settings) -> ResumeImageStorage:
    backend = settings.resume_image_storage_backend.strip().lower()
    if backend == "local":
        return LocalResumeImageStorage(settings.resume_image_storage_dir)

    if backend == "s3":
        required_values = {
            "S3_ENDPOINT_URL": settings.resume_image_s3_endpoint_url,
            "S3_BUCKET_NAME": settings.resume_image_s3_bucket_name,
            "S3_ACCESS_KEY_ID": settings.resume_image_s3_access_key_id,
            "S3_SECRET_ACCESS_KEY": settings.resume_image_s3_secret_access_key,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"S3 resume image storage is missing required variables: {', '.join(missing)}.",
            )

        try:
            return S3ResumeImageStorage(
                endpoint_url=settings.resume_image_s3_endpoint_url or "",
                region_name=settings.resume_image_s3_region,
                bucket_name=settings.resume_image_s3_bucket_name or "",
                access_key_id=settings.resume_image_s3_access_key_id or "",
                secret_access_key=settings.resume_image_s3_secret_access_key or "",
                key_prefix=settings.resume_image_s3_key_prefix,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="RESUME_IMAGE_STORAGE_BACKEND must be either 'local' or 's3'.",
    )


async def cleanup_stored_resume_image(storage: ResumeImageStorage, image: Any) -> None:
    try:
        await storage.delete(image)
    except Exception:
        logger.warning("Failed to clean up uploaded resume image after a later error.", exc_info=True)


def build_resume_image_response(document: dict[str, Any], image_url: str) -> ResumeParseResponse:
    response_document = dict(document)
    response_document["avatar"] = image_url
    response_document["withPhoto"] = True

    try:
        return ResumeParseResponse.model_validate(response_document)
    except ValidationError as exc:
        logger.exception("Saved resume image but failed to validate the resume image response.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Resume image was saved, but the saved resume document could not be returned "
                "because it does not match the API response schema."
            ),
        ) from exc


def build_resume_image_url(request: Request, settings: Settings, filename: str) -> str:
    public_api_base_url = (settings.public_api_base_url or "").strip().rstrip("/")
    if public_api_base_url:
        path = request.app.url_path_for("get_resume_image", filename=filename)
        return f"{public_api_base_url}{path}"

    return str(request.url_for("get_resume_image", filename=filename))


async def read_rephrase_request(request: Request) -> ResumeRephraseRequest:
    body = await request.body()
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()

    try:
        body_text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Request body must be UTF-8 encoded.",
        ) from exc

    if content_type == "text/plain":
        payload_data: object = {"text": body_text}
    else:
        try:
            payload_data = json.loads(body_text, strict=False)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": (
                        "Request body must be a JSON object with a text field. "
                        "Escape raw newline, tab, and other control characters, "
                        "or build the request body with JSON.stringify."
                    ),
                    "error": exc.msg,
                    "position": exc.pos,
                },
            ) from exc

    try:
        return ResumeRephraseRequest.model_validate(payload_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc


async def read_resume_profile_request(request: Request) -> ResumeProfile:
    body = await request.body()
    try:
        payload_data: Any = json.loads(body.decode("utf-8"), strict=False)
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Request body must be UTF-8 encoded.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Request body must be a JSON object containing a resume profile.",
                "error": exc.msg,
                "position": exc.pos,
            },
        ) from exc

    try:
        return ResumeProfile.model_validate(normalize_resume_profile_payload(payload_data))
    except ValidationError as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc


@router.post("/parse", response_model=ResumeParseResponse)
async def parse_resume(
    file: UploadFile = File(...),
    jobDescription: str | None = Form(default=None),
    userId: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
) -> ResumeParseResponse:
    content, extension = await read_and_validate_file(file, settings.max_file_size_bytes)
    extractor = DocumentTextExtractor(settings=settings)
    resume_text, extraction_method = await extractor.extract_with_fallback(content, extension)

    if not resume_text or not resume_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Resume text extraction failed. The file may be empty, corrupted, or image-only without OCR fallback enabled.",
        )

    validate_resume_document(resume_text)
    try:
        llm_client = get_llm_client(settings)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    parser = ResumeParserService(llm_client)
    profile = await parser.parse(resume_text, jobDescription.strip() if jobDescription else None)
    normalized_user_id = normalize_user_id(userId)
    metadata = {
        "filename": file.filename,
        "fileType": extension,
        "fileSizeBytes": len(content),
        "extractedTextCharacters": len(resume_text),
        "jobDescriptionProvided": bool(jobDescription and jobDescription.strip()),
        "extractionMethod": extraction_method,
    }

    try:
        repository = get_resume_repository(settings)
        resume_id = await repository.save(
            profile,
            metadata,
            jobDescription.strip() if jobDescription else None,
            user_id=normalized_user_id,
        )
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to save parsed resume to MongoDB.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is configured but failed to save the parsed resume. Check MONGO_URI, database, collection, and write permissions.",
        ) from exc

    return ResumeParseResponse(
        id=resume_id,
        profile=profile,
        metadata=metadata,
        resumeId=resume_id,
        userId=normalized_user_id,
        version=1,
        status="parsed",
    )


@router.get("", response_model=list[ResumeParseResponse])
async def list_resumes(
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    userId: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> list[ResumeParseResponse]:
    try:
        repository = get_resume_repository(settings)
        return await repository.list(limit=limit, skip=skip, user_id=normalize_user_id(userId))
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to list parsed resumes from MongoDB.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is configured but failed to list parsed resumes.",
        ) from exc


@router.get("/images/{filename}", name="get_resume_image")
async def get_resume_image(
    filename: str,
    settings: Settings = Depends(get_settings),
) -> Response:
    storage = get_resume_image_storage(settings)
    image = await storage.read_public_image(filename)
    return Response(content=image.content, media_type=image.content_type)


@router.get("/{resume_id}", response_model=ResumeParseResponse)
async def get_resume(
    resume_id: str,
    userId: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> ResumeParseResponse:
    try:
        repository = get_resume_repository(settings)
        document = await repository.get(resume_id, user_id=normalize_user_id(userId))
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to fetch resume from MongoDB.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is configured but failed to fetch the resume.",
        ) from exc

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume was not found.",
        )

    return document


@router.post("/{resume_id}/image", response_model=ResumeParseResponse)
async def upload_resume_image(
    resume_id: str,
    request: Request,
    userId: str | None = Query(default=None),
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> ResumeParseResponse:
    normalized_user_id = normalize_user_id(userId)
    try:
        repository = get_resume_repository(settings)
        existing_document = await repository.get(resume_id, user_id=normalized_user_id)
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to fetch resume before uploading image.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is configured but failed to fetch the resume.",
        ) from exc

    if existing_document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume was not found.",
        )

    storage = get_resume_image_storage(settings)
    try:
        stored_image = await storage.save_upload(resume_id, file, settings.resume_image_max_size_bytes)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save uploaded resume image to configured storage.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume image storage is configured but failed to save the uploaded file.",
        ) from exc

    image_url = build_resume_image_url(request, settings, stored_image.filename)
    image_metadata = {
        "url": image_url,
        "filename": stored_image.filename,
        "objectKey": stored_image.key,
        "storageBackend": stored_image.backend,
        "originalFilename": file.filename,
        "contentType": stored_image.content_type,
        "sizeBytes": stored_image.size_bytes,
    }

    try:
        await repository.save_image(resume_id, image_url, image_metadata, user_id=normalized_user_id)
    except ResumeNotFoundError as exc:
        await cleanup_stored_resume_image(storage, stored_image)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        await cleanup_stored_resume_image(storage, stored_image)
        logger.exception("Failed to save resume image URL to MongoDB.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is configured but failed to save the resume image URL.",
        ) from exc

    return build_resume_image_response(existing_document, image_url)


@router.post("/{resume_id}/edits", response_model=ResumeParseResponse)
async def save_edited_resume(
    resume_id: str,
    request: Request,
    userId: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> ResumeParseResponse:
    profile = await read_resume_profile_request(request)

    try:
        repository = get_resume_repository(settings)
        return await repository.save_edited(resume_id, profile, user_id=normalize_user_id(userId))
    except ResumeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to save edited resume to MongoDB.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is configured but failed to save the edited resume.",
        ) from exc


@router.post(
    "/rephrase",
    response_model=ResumeRephraseResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": ResumeRephraseRequest.model_json_schema()},
                "text/plain": {"schema": {"type": "string", "minLength": 1, "maxLength": 8000}},
            },
        }
    },
)
async def rephrase_resume_text(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ResumeRephraseResponse:
    payload = await read_rephrase_request(request)
    try:
        llm_client = get_llm_client(settings)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    rephraser = ResumeRephraseService(llm_client)
    return await rephraser.rephrase(payload.text)
