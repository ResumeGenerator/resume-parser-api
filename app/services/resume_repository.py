from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import Settings
from app.models.resume_schema import ResumeProfile


class ResumeRepositoryNotConfiguredError(RuntimeError):
    pass


class MongoResumeRepository:
    def __init__(self, settings: Settings):
        if not settings.mongodb_uri:
            raise ResumeRepositoryNotConfiguredError("MONGO_URI is required to store parsed resumes.")

        self.client: AsyncIOMotorClient = AsyncIOMotorClient(settings.mongodb_uri)
        self.database_name = settings.mongodb_database
        self.collection_name = settings.mongodb_resume_collection
        self.collection: AsyncIOMotorCollection = self.client[self.database_name][self.collection_name]

    async def initialize(self) -> None:
        await self.client.admin.command("ping")
        await self.collection.create_index("createdAt")
        await self.collection.create_index("profile.candidateProfile.email")
        await self.collection.create_index("metadata.filename")

    async def save(
        self,
        profile: ResumeProfile,
        metadata: dict[str, Any],
        job_description: str | None,
    ) -> str:
        now = datetime.now(UTC)
        document = {
            "profile": profile.model_dump(mode="json"),
            "metadata": metadata,
            "source": {
                "jobDescription": job_description,
            },
            "createdAt": now,
            "updatedAt": now,
        }
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)

    async def get_by_id(self, resume_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(resume_id):
            return None

        document = await self.collection.find_one({"_id": ObjectId(resume_id)})
        if document is None:
            return None

        return serialize_resume_document(document)

    def close(self) -> None:
        self.client.close()


def serialize_resume_document(document: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(document)
    serialized["id"] = str(serialized.pop("_id"))

    for key in ("createdAt", "updatedAt"):
        value = serialized.get(key)
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()

    return serialized
