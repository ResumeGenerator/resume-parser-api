import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.database import get_resume_repository
from app.core.llm_client import get_llm_client
from app.models.resume_schema import ResumeParseResponse, ResumeProfile, ResumeRephraseRequest, ResumeRephraseResponse
from app.services.document_text_extractor import DocumentTextExtractor
from app.services.resume_parser import ResumeParserService, normalize_resume_profile_payload
from app.services.resume_rephraser import ResumeRephraseService
from app.services.resume_repository import ResumeNotFoundError, ResumeRepositoryNotConfiguredError
from app.utils.file_validator import read_and_validate_file
from app.utils.resume_detector import validate_resume_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resumes", tags=["resumes"])
HTTP_422_UNPROCESSABLE_CONTENT = 422


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
        resume_id = await repository.save(profile, metadata, jobDescription.strip() if jobDescription else None)
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
        version=1,
        status="parsed",
    )


@router.get("", response_model=list[ResumeParseResponse])
async def list_resumes(
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
) -> list[ResumeParseResponse]:
    try:
        repository = get_resume_repository(settings)
        return await repository.list(limit=limit, skip=skip)
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


@router.get("/{resume_id}", response_model=ResumeParseResponse)
async def get_resume(
    resume_id: str,
    settings: Settings = Depends(get_settings),
) -> ResumeParseResponse:
    try:
        repository = get_resume_repository(settings)
        document = await repository.get(resume_id)
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


@router.post("/{resume_id}/edits", response_model=ResumeParseResponse)
async def save_edited_resume(
    resume_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ResumeParseResponse:
    profile = await read_resume_profile_request(request)

    try:
        repository = get_resume_repository(settings)
        return await repository.save_edited(resume_id, profile)
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
