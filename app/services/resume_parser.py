from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.llm_client import BaseLLMClient
from app.models.resume_schema import ResumeProfile, parse_optional_float


def normalize_resume_profile_payload(raw_profile: object) -> object:
    if not isinstance(raw_profile, dict):
        return raw_profile

    candidate_profile = raw_profile.get("candidateProfile")
    if isinstance(candidate_profile, dict) and "totalExperienceYears" in candidate_profile:
        candidate_profile["totalExperienceYears"] = parse_optional_float(
            candidate_profile["totalExperienceYears"]
        )

    return raw_profile


class ResumeParserService:
    def __init__(self, llm_client: BaseLLMClient):
        self.llm_client = llm_client

    async def parse(self, resume_text: str, job_description: str | None) -> ResumeProfile:
        raw_profile = await self.llm_client.extract_resume_profile(resume_text, job_description)
        raw_profile = normalize_resume_profile_payload(raw_profile)
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
