from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.llm_client import BaseLLMClient
from app.models.resume_schema import ResumeProfile


class ResumeParserService:
    def __init__(self, llm_client: BaseLLMClient):
        self.llm_client = llm_client

    async def parse(self, resume_text: str, job_description: str | None) -> ResumeProfile:
        raw_profile = await self.llm_client.extract_resume_profile(resume_text, job_description)
        try:
            return ResumeProfile.model_validate(raw_profile)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "LLM response did not match the resume schema.",
                    "errors": exc.errors(),
                },
            ) from exc

