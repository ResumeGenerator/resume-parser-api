from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.core.config import Settings, get_settings
from app.core.database import get_resume_repository
from app.core.llm_client import get_llm_client
from app.models.resume_schema import ResumeDocumentResponse, ResumeListResponse, ResumeParseResponse
from app.services.document_text_extractor import DocumentTextExtractor
from app.services.resume_parser import ResumeParserService
from app.services.resume_repository import ResumeRepositoryNotConfiguredError
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
    extractor = DocumentTextExtractor(settings=settings)
    resume_text, extraction_method = await extractor.extract_with_fallback(content, extension)
    
    # Validate extracted text is not empty
    if not resume_text or not resume_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Resume text extraction failed. The file may be empty, corrupted, or image-only without OCR fallback enabled.",
        )
    
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

    return ResumeParseResponse(
        id=resume_id,
        profile=profile,
        metadata=metadata,
    )


@router.get("", response_model=ResumeListResponse)
async def list_resumes(
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
) -> ResumeListResponse:
    try:
        repository = get_resume_repository(settings)
        items = await repository.list_saved(limit=limit, skip=skip)
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return ResumeListResponse(items=items, count=len(items))


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
