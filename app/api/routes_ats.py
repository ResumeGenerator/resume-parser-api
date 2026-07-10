import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.core.database import get_resume_repository
from app.models.ats_schema import AtsScoreResponse
from app.services.ats_score_service import calculate_ats_score
from app.services.resume_repository import ResumeRepositoryNotConfiguredError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resumes", tags=["ats"])
ALLOWED_SOURCES = {"parsed"}


@router.get("/{resumeId}/ats-score", response_model=AtsScoreResponse)
async def get_ats_score(
    resumeId: str,
    source: str = Query(default="parsed"),
    userId: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> AtsScoreResponse:
    normalized_source = source.strip().casefold()
    normalized_user_id = _normalize_user_id(userId)
    if normalized_source not in ALLOWED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source must be 'parsed'.",
        )

    try:
        repository = get_resume_repository(settings)
        resume_document = await repository.get(resumeId, user_id=normalized_user_id)
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to fetch resume before ATS scoring.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is configured but failed to fetch the resume for ATS scoring.",
        ) from exc

    if resume_document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume was not found.",
        )

    try:
        result = calculate_ats_score(_resume_content_for_scoring(resume_document))
    except Exception as exc:
        logger.exception("Failed to calculate ATS score.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate ATS score.",
        ) from exc

    response = AtsScoreResponse.model_validate(
        {
            "resumeId": _stable_resume_id(resume_document, resumeId),
            "source": normalized_source,
            **result,
        }
    )

    try:
        stored = await repository.save_ats_calculation(
            resumeId,
            response.model_dump(exclude={"resumeId", "source"}),
            user_id=normalized_user_id,
        )
    except Exception as exc:
        logger.exception("Failed to store the parsed resume ATS calculation.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ATS score was calculated but could not be stored on the parsed resume.",
        ) from exc

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume was not found while storing the ATS calculation.",
        )

    return response


def _resume_content_for_scoring(document: dict[str, Any]) -> dict[str, Any]:
    profile = document.get("profile")
    if isinstance(profile, dict) and profile:
        return profile
    return document


def _stable_resume_id(document: dict[str, Any], fallback: str) -> str:
    return str(document.get("resumeId") or document.get("id") or document.get("_id") or fallback)


def _normalize_user_id(user_id: str | None) -> str | None:
    if user_id is None:
        return None

    normalized = user_id.strip()
    return normalized or None
