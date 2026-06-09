import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings, get_settings


SYSTEM_PROMPT = """You are a production resume parsing engine.
Return valid JSON only. Do not wrap the JSON in markdown.
Use only the resume text supplied by the user. Do not invent missing details.
For missing scalar data return null. For missing collections return [].
Extract data exactly into the requested predefined resume schema.
Include ATS analysis, job-fit analysis when a job description is provided, resume generation strategy,
achievement bank, and reusable resume blocks for a future ATS-compliant resume generation service.
Safe rewrite suggestions must preserve the candidate's truthful experience and must not fabricate metrics."""


USER_PROMPT_TEMPLATE = """Resume text:
{resume_text}

Optional job description:
{job_description}

Return JSON with this top-level shape and keys:
{{
  "candidateProfile": {{}},
  "careerClassification": {{}},
  "careerProgression": [],
  "professionalSummaryPoints": [],
  "coreSkills": [],
  "skillsMatrix": {{
    "technicalSkills": [],
    "domainSkills": [],
    "toolsAndPlatforms": [],
    "leadershipAndSoftSkills": [],
    "languages": []
  }},
  "workExperience": [],
  "projectsOrCaseStudies": [],
  "achievementBank": [],
  "education": [],
  "certificationsAndLicenses": [],
  "affiliationsAndMemberships": [],
  "awardsAndRecognition": [],
  "volunteerExperience": [],
  "publicationsAndSpeaking": [],
  "resumeBlocks": {{}},
  "recommendedResumeVariants": [],
  "atsAnalysis": {{}},
  "jobFitAnalysis": null,
  "resumeStrengths": [],
  "missingOrWeakAreas": [],
  "atsKeywordsFound": [],
  "jobDescriptionKeywordMatches": [],
  "jobDescriptionKeywordGaps": [],
  "resumeGenerationStrategy": {{}},
  "safeRewriteSuggestions": []
}}"""


class BaseLLMClient(ABC):
    @abstractmethod
    async def extract_resume_profile(self, resume_text: str, job_description: str | None) -> dict[str, Any]:
        raise NotImplementedError


def build_user_prompt(resume_text: str, job_description: str | None) -> str:
    return USER_PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        job_description=job_description or "null",
    )


def parse_json_response(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM returned a non-JSON response.",
            )
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM returned invalid JSON.",
            ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM JSON response must be an object.",
        )
    return parsed


class OpenAIClient(BaseLLMClient):
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model

    async def extract_resume_profile(self, resume_text: str, job_description: str | None) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(resume_text, job_description)},
            ],
            "temperature": 0.1,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)

        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OpenAI request failed: {response.text}")

        content = response.json()["choices"][0]["message"]["content"]
        return parse_json_response(content)


class AzureOpenAIClient(BaseLLMClient):
    def __init__(self, settings: Settings):
        required = {
            "AZURE_OPENAI_ENDPOINT": settings.azure_openai_endpoint,
            "AZURE_OPENAI_API_KEY": settings.azure_openai_api_key,
            "AZURE_OPENAI_DEPLOYMENT": settings.azure_openai_deployment,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"{', '.join(missing)} required when LLM_PROVIDER=azure_openai.")
        self.endpoint = settings.azure_openai_endpoint.rstrip("/")  # type: ignore[union-attr]
        self.api_key = settings.azure_openai_api_key
        self.deployment = settings.azure_openai_deployment
        self.api_version = settings.azure_openai_api_version

    async def extract_resume_profile(self, resume_text: str, job_description: str | None) -> dict[str, Any]:
        url = (
            f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions"
            f"?api-version={self.api_version}"
        )
        payload = {
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(resume_text, job_description)},
            ],
            "temperature": 0.1,
        }
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Azure OpenAI request failed: {response.text}")

        content = response.json()["choices"][0]["message"]["content"]
        return parse_json_response(content)


class OllamaClient(BaseLLMClient):
    def __init__(self, settings: Settings):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model

    async def extract_resume_profile(self, resume_text: str, job_description: str | None) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(resume_text, job_description)},
            ],
            "options": {"temperature": 0.1},
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)

        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Ollama request failed: {response.text}")

        content = response.json()["message"]["content"]
        return parse_json_response(content)


def get_llm_client(settings: Settings | None = None) -> BaseLLMClient:
    settings = settings or get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "openai":
        return OpenAIClient(settings)
    if provider in {"azure", "azure_openai"}:
        return AzureOpenAIClient(settings)
    if provider == "ollama":
        return OllamaClient(settings)

    raise RuntimeError(f"Unsupported LLM_PROVIDER '{settings.llm_provider}'.")

