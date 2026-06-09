from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.llm_client import BaseLLMClient, get_llm_client
from app.models.resume_schema import ResumeParseResponse
from app.services.resume_parser import ResumeParserService
from app.services.text_extractor import extract_resume_text
from app.utils.file_validator import read_and_validate_file

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


def llm_client_dependency() -> BaseLLMClient:
    try:
        return get_llm_client()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/parse", response_model=ResumeParseResponse)
async def parse_resume(
    file: UploadFile = File(...),
    jobDescription: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    llm_client: BaseLLMClient = Depends(llm_client_dependency),
) -> ResumeParseResponse:
    content, extension = await read_and_validate_file(file, settings.max_file_size_bytes)
    resume_text = await run_in_threadpool(extract_resume_text, content, extension)
    parser = ResumeParserService(llm_client)
    profile = await parser.parse(resume_text, jobDescription.strip() if jobDescription else None)

    return ResumeParseResponse(
        profile=profile,
        metadata={
            "filename": file.filename,
            "fileType": extension,
            "fileSizeBytes": len(content),
            "extractedTextCharacters": len(resume_text),
            "jobDescriptionProvided": bool(jobDescription and jobDescription.strip()),
        },
    )
