from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.database import get_resume_repository
from app.core.llm_client import get_llm_client
from app.models.resume_schema import ResumeDocumentResponse, ResumeParseResponse
from app.services.resume_parser import ResumeParserService
from app.services.resume_repository import ResumeRepositoryNotConfiguredError
from app.services.text_extractor import extract_resume_text
from app.utils.file_validator import read_and_validate_file
from app.utils.resume_detector import validate_resume_document

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.post("/parse", response_model=ResumeParseResponse)
async def parse_resume(
    file: UploadFile = File(...),
    jobDescription: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
) -> ResumeParseResponse:
    content, extension = await read_and_validate_file(file, settings.max_file_size_bytes)
    resume_text = await run_in_threadpool(extract_resume_text, content, extension)
    validate_resume_document(resume_text)
    try:
        llm_client = get_llm_client()
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
    }

    try:
        repository = get_resume_repository(settings)
        resume_id = await repository.save(profile, metadata, jobDescription.strip() if jobDescription else None)
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return ResumeParseResponse(
        id=resume_id,
        profile=profile,
        metadata=metadata,
    )


@router.get("/{resume_id}", response_model=ResumeDocumentResponse)
async def get_resume(
    resume_id: str,
    settings: Settings = Depends(get_settings),
) -> ResumeDocumentResponse:
    try:
        repository = get_resume_repository(settings)
        document = await repository.get_by_id(resume_id)
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed resume was not found.",
        )

    return ResumeDocumentResponse.model_validate(document)
