import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.core.resume_prompt import SYSTEM_PROMPT, build_user_prompt


class BaseLLMClient(ABC):
    @abstractmethod
    async def extract_resume_profile(self, resume_text: str, job_description: str | None) -> dict[str, Any]:
        raise NotImplementedError


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


class GeminiClient(BaseLLMClient):
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model

    async def extract_resume_profile(self, resume_text: str, job_description: str | None) -> dict[str, Any]:
        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_user_prompt(resume_text, job_description)}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }
        headers = {"Content-Type": "application/json"}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, json=payload, headers=headers, params={"key": self.api_key})

        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Gemini request failed: {response.text}")

        content = self._extract_text(response.json())
        return parse_json_response(content)

    @staticmethod
    def _extract_text(response_payload: dict[str, Any]) -> str:
        try:
            parts = response_payload["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini returned an unexpected response shape.",
            ) from exc

        text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        content = "".join(text_parts).strip()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini returned an empty response.",
            )
        return content


def get_llm_client(settings: Settings | None = None) -> BaseLLMClient:
    settings = settings or get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "openai":
        return OpenAIClient(settings)
    if provider == "gemini":
        return GeminiClient(settings)

    raise RuntimeError(f"Unsupported LLM_PROVIDER '{settings.llm_provider}'.")
