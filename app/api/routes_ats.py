import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.core.database import get_resume_repository
from app.models.ats_schema import AtsScoreResponse, CompareAtsScoreResponse
from app.services.ats_score_service import calculate_ats_score, compare_ats_scores
from app.services.resume_repository import ResumeRepositoryNotConfiguredError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resumes", tags=["ats"])
ALLOWED_SOURCES = {"parsed", "edited"}


@router.get("/{resumeId}/ats-score", response_model=AtsScoreResponse)
async def get_ats_score(
    resumeId: str,
    source: str = Query(default="edited"),
    settings: Settings = Depends(get_settings),
) -> AtsScoreResponse:
    normalized_source = source.strip().casefold()
    if normalized_source not in ALLOWED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source must be either 'parsed' or 'edited'.",
        )

    try:
        repository = get_resume_repository(settings)
        resume_document = await repository.get_resume_by_id(resumeId, normalized_source)
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

    return AtsScoreResponse.model_validate(
        {
            "resumeId": _stable_resume_id(resume_document, resumeId),
            "source": normalized_source,
            **result,
        }
    )


@router.get("/{resumeId}/compare-ats-score", response_model=CompareAtsScoreResponse)
async def compare_resume_ats_score(
    resumeId: str,
    settings: Settings = Depends(get_settings),
) -> CompareAtsScoreResponse:
    try:
        repository = get_resume_repository(settings)
        parsed_resume, edited_resume = await repository.get_parsed_and_edited_resume(resumeId)
    except ResumeRepositoryNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to fetch resumes before ATS comparison.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is configured but failed to fetch resumes for ATS comparison.",
        ) from exc

    if parsed_resume is None or edited_resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed and edited resumes are required for ATS score comparison.",
        )

    try:
        result = compare_ats_scores(
            _resume_content_for_scoring(parsed_resume),
            _resume_content_for_scoring(edited_resume),
        )
    except Exception as exc:
        logger.exception("Failed to compare ATS scores.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare ATS scores.",
        ) from exc

    return CompareAtsScoreResponse.model_validate(
        {
            "resumeId": _stable_resume_id(parsed_resume, resumeId),
            **result,
        }
    )


def _resume_content_for_scoring(document: dict[str, Any]) -> dict[str, Any]:
    profile = document.get("profile")
    if isinstance(profile, dict) and profile:
        return profile
    return document


def _stable_resume_id(document: dict[str, Any], fallback: str) -> str:
    return str(document.get("resumeId") or document.get("id") or document.get("_id") or fallback)
