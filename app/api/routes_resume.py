import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.database import get_resume_repository
from app.core.llm_client import get_llm_client
from app.models.resume_schema import ResumeParseResponse, ResumeRephraseRequest, ResumeRephraseResponse
from app.services.document_text_extractor import DocumentTextExtractor
from app.services.resume_parser import ResumeParserService
from app.services.resume_rephraser import ResumeRephraseService
from app.services.resume_repository import ResumeRepositoryNotConfiguredError
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
