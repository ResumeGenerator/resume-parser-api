import logging

from app.core.config import Settings, get_settings
from app.services.resume_repository import MongoResumeRepository

logger = logging.getLogger(__name__)

_resume_repository: MongoResumeRepository | None = None


def get_resume_repository(settings: Settings | None = None) -> MongoResumeRepository:
    global _resume_repository

    if _resume_repository is None:
        _resume_repository = MongoResumeRepository(settings or get_settings())

    return _resume_repository


async def initialize_database() -> None:
    settings = get_settings()
    if not settings.mongodb_uri:
        return

    try:
        repository = get_resume_repository(settings)
        await repository.initialize()
        logger.info(
            "Database initialised successfully: database=%r resume_collection=%r",
            repository.database_name,
            repository.collection_name,
        )
    except Exception as exc:
        logger.error(
            "Database initialisation failed — the app will start without a "
            "database connection. Endpoints that require MongoDB will be "
            "unavailable until the connection is restored. Error: %s",
            exc,
        )


def close_database() -> None:
    global _resume_repository

    if _resume_repository is not None:
        _resume_repository.close()
        _resume_repository = None
