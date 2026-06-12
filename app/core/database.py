from app.core.config import Settings, get_settings
from app.services.resume_repository import MongoResumeRepository

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

    repository = get_resume_repository(settings)
    await repository.initialize()


def close_database() -> None:
    global _resume_repository

    if _resume_repository is not None:
        _resume_repository.close()
        _resume_repository = None
