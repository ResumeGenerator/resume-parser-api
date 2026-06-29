import re

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.llm_client import BaseLLMClient
from app.models.resume_schema import ResumeProfile


_SUMMARY_HEADING_RE = re.compile(
    r"^\s*(?:profile\s+summary|professional\s+summary|summary|profile)\s*[:\n]+",
    flags=re.IGNORECASE,
)
_LINE_ITEM_DELIMITER_RE = re.compile(
    r"(?m)(?:^|\n)\s*(?:[-*•◦▪▫‣⁃∙●○■□◆◇❖➢➤✓✔]|\d+[.)])\s+"
)
_INLINE_GRAPHIC_DELIMITER_RE = re.compile(r"\s*[•◦▪▫‣⁃∙●○■□◆◇❖➢➤✓✔]\s+")
_INLINE_HYPHEN_DELIMITER_RE = re.compile(r"\s+-\s+(?=[A-Z0-9])")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_summary_item_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip(" \t\r\n-*:;")


def split_summary_items(value: str) -> list[str]:
    text = _SUMMARY_HEADING_RE.sub("", value.strip(), count=1)
    if not text:
        return []

    parts = [part for part in _LINE_ITEM_DELIMITER_RE.split(text) if part.strip()]
    if len(parts) <= 1:
        parts = [part for part in _INLINE_GRAPHIC_DELIMITER_RE.split(text) if part.strip()]
    if len(parts) <= 1 and text.lstrip().startswith("- "):
        parts = [part for part in _INLINE_HYPHEN_DELIMITER_RE.split(text) if part.strip()]

    return [normalized for part in parts if (normalized := _normalize_summary_item_text(part))]


def normalize_summary_section_items(raw_profile: dict) -> None:
    data = raw_profile.get("data")
    if not isinstance(data, dict):
        return

    sections = data.get("sections")
    if not isinstance(sections, list):
        return

    for section in sections:
        if not isinstance(section, dict):
            continue

        section_type = section.get("type")
        if not isinstance(section_type, str) or section_type.strip().lower() != "summary":
            continue

        items = section.get("items")
        if isinstance(items, str):
            summary_items = split_summary_items(items)
            if len(summary_items) > 1:
                section["items"] = summary_items
            continue

        if isinstance(items, list):
            summary_items: list[object] = []
            changed = False
            for item in items:
                if not isinstance(item, str):
                    summary_items.append(item)
                    continue

                split_items = split_summary_items(item)
                if len(split_items) > 1:
                    summary_items.extend(split_items)
                    changed = True
                elif split_items:
                    summary_items.append(split_items[0])
                else:
                    changed = True

            if changed:
                section["items"] = summary_items


def normalize_resume_profile_payload(raw_profile: object) -> object:
    if not isinstance(raw_profile, dict):
        return raw_profile

    wrapped_profile = raw_profile.get("profile")
    if isinstance(wrapped_profile, dict):
        normalize_summary_section_items(wrapped_profile)
        return wrapped_profile

    normalize_summary_section_items(raw_profile)
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
