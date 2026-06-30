import re
from typing import Any, Protocol

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.models.resume_schema import ResumeRephraseResponse


class ResumeRephraseLLMClient(Protocol):
    async def rephrase_resume_text(self, text: str) -> dict[str, Any]:
        raise NotImplementedError


_NON_RESUME_RESPONSE_RE = re.compile(
    r"\b(as an ai|i can(?:not|'t)?|here(?:'s| is)|rephrased version|resume version|professional version)\b",
    flags=re.IGNORECASE,
)
_TEXT_SEPARATOR_RE = re.compile(r"((?:(?:\r\n)|\r|\n)+)")


def validate_resume_rephrase_output(response: ResumeRephraseResponse) -> None:
    if _NON_RESUME_RESPONSE_RE.search(response.rephrasedText):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM response included non-resume commentary.",
        )


class ResumeRephraseService:
    def __init__(self, llm_client: ResumeRephraseLLMClient):
        self.llm_client = llm_client

    async def _rephrase_text_block(self, text: str) -> ResumeRephraseResponse:
        raw_response = await self.llm_client.rephrase_resume_text(text)
        try:
            response = ResumeRephraseResponse.model_validate(raw_response)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "LLM response did not match the resume rephrase schema.",
                    "errors": exc.errors(),
                },
            ) from exc

        validate_resume_rephrase_output(response)
        return response

    async def rephrase(self, text: str) -> ResumeRephraseResponse:
        parts = _TEXT_SEPARATOR_RE.split(text)
        text_block_count = sum(1 for index, part in enumerate(parts) if index % 2 == 0 and part.strip())

        if text_block_count <= 1:
            return await self._rephrase_text_block(text)

        rephrased_parts: list[str] = []
        for index, part in enumerate(parts):
            if index % 2 == 1 or not part.strip():
                rephrased_parts.append(part)
                continue

            response = await self._rephrase_text_block(part.strip())
            rephrased_parts.append(response.rephrasedText)

        return ResumeRephraseResponse(rephrasedText="".join(rephrased_parts).strip())
