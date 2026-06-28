import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import Settings
from app.models.resume_schema import ResumeProfile

logger = logging.getLogger(__name__)


class ResumeRepositoryNotConfiguredError(RuntimeError):
    pass


class MongoResumeRepository:
    def __init__(self, settings: Settings):
        if not settings.mongodb_uri:
            raise ResumeRepositoryNotConfiguredError("MONGO_URI is required to store parsed resumes.")

        self.client: AsyncIOMotorClient = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
        )
        self.database_name = settings.mongodb_database
        self.collection_name = settings.mongodb_resume_collection
        self.collection: AsyncIOMotorCollection = self.client[self.database_name][self.collection_name]

    async def initialize(self) -> None:
        await self.client.admin.command("ping")
        await self.collection.create_index("createdAt")
        await self.collection.create_index("status")
        await self.collection.create_index("profile.data.email")
        await self.collection.create_index("metadata.filename")

    async def save(
        self,
        profile: ResumeProfile,
        metadata: dict[str, Any],
        job_description: str | None,
    ) -> str:
        now = datetime.now(UTC)
        resume_object_id = ObjectId()
        resume_id = str(resume_object_id)
        document = {
            "_id": resume_object_id,
            "resumeId": resume_id,
            "version": 1,
            "status": "parsed",
            "profile": profile.model_dump(mode="json"),
            "metadata": metadata,
            "source": {
                "jobDescription": job_description,
                "createdFrom": "parse",
            },
            "createdAt": now,
            "updatedAt": now,
        }
        result = await self.collection.insert_one(document)
        logger.info(
            "Saved parsed resume to MongoDB database=%r collection=%r resume_id=%s inserted_id=%s",
            self.database_name,
            self.collection_name,
            resume_id,
            result.inserted_id,
        )
        return str(result.inserted_id)

    def close(self) -> None:
        self.client.close()
