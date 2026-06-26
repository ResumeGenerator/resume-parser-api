from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import Settings
from app.models.resume_schema import ResumeProfile, ResumeTemplateSaveRequest


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
        self.edited_collection_name = settings.mongodb_edited_resume_collection
        self.edited_collection: AsyncIOMotorCollection = self.client[self.database_name][self.edited_collection_name]
        self.template_collection_name = settings.mongodb_template_resume_collection
        self.template_collection: AsyncIOMotorCollection = self.client[self.database_name][self.template_collection_name]

    async def initialize(self) -> None:
        await self.client.admin.command("ping")
        await self.collection.create_index("createdAt")
        await self.collection.create_index("profile.candidateProfile.email")
        await self.collection.create_index("metadata.filename")
        await self.edited_collection.create_index("createdAt")
        await self.edited_collection.create_index("originalResumeId")
        await self.edited_collection.create_index("profile.candidateProfile.email")
        await self.template_collection.create_index("createdAt")
        await self.template_collection.create_index("originalResumeId")
        await self.template_collection.create_index("templateResume.template")
        await self.template_collection.create_index("templateResume.data.email")

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
            edited_document = await self.edited_collection.find_one({"_id": ObjectId(resume_id)})
            return serialize_resume_document(edited_document) if edited_document is not None else None

        edited_document = await self.get_latest_edited_copy(resume_id)
        if edited_document is not None:
            serialized_edited_document = serialize_resume_document(edited_document)
            serialized_edited_document["id"] = str(document["_id"])
            return serialized_edited_document

        return serialize_resume_document(document)

    async def save_edited_copy(
        self,
        original_resume_id: str,
        profile: ResumeProfile,
        metadata: dict[str, Any],
        source: dict[str, Any],
    ) -> dict[str, Any]:
        if not ObjectId.is_valid(original_resume_id):
            raise ValueError("Original resume id is not valid.")

        now = datetime.now(UTC)
        document = {
            "originalResumeId": original_resume_id,
            "profile": profile.model_dump(mode="json"),
            "metadata": {
                **metadata,
                "editedFromResumeId": original_resume_id,
            },
            "source": source,
            "createdAt": now,
            "updatedAt": now,
        }
        result = await self.edited_collection.insert_one(document)
        saved_document = await self.edited_collection.find_one({"_id": result.inserted_id})

        return serialize_resume_document(saved_document or document | {"_id": result.inserted_id})

    async def save_template_resume(
        self,
        original_resume_id: str,
        template_resume: ResumeTemplateSaveRequest,
    ) -> dict[str, Any]:
        if not ObjectId.is_valid(original_resume_id):
            raise ValueError("Original resume id is not valid.")

        now = datetime.now(UTC)
        metadata = {
            **template_resume.metadata,
            "template": template_resume.template,
            "format": template_resume.format,
            "originalResumeId": original_resume_id,
        }
        source = {
            **template_resume.source,
            "originalResumeId": original_resume_id,
        }
        document = {
            "originalResumeId": original_resume_id,
            "templateResume": template_resume.model_dump(mode="json"),
            "metadata": metadata,
            "source": source,
            "createdAt": now,
            "updatedAt": now,
        }
        result = await self.template_collection.insert_one(document)
        saved_document = await self.template_collection.find_one({"_id": result.inserted_id})

        return serialize_resume_document(saved_document or document | {"_id": result.inserted_id})

    async def get_latest_template_resume(self, original_resume_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(original_resume_id):
            return None

        document = await self.template_collection.find_one(
            {"originalResumeId": original_resume_id},
            sort=[("updatedAt", -1), ("createdAt", -1)],
        )

        return serialize_resume_document(document) if document is not None else None

    async def list_saved(self, limit: int = 100, skip: int = 0) -> list[dict[str, Any]]:
        projection = {
            "metadata.filename": 1,
            "profile.candidateProfile.fullName": 1,
            "profile.candidateProfile.email": 1,
            "profile.candidateProfile.currentTitle": 1,
            "createdAt": 1,
            "updatedAt": 1,
        }
        originals = [
            document
            async for document in (
            self.collection.find({}, projection)
            .sort("createdAt", -1)
            .skip(skip)
            .limit(limit)
            )
        ]
        if not originals:
            return []

        original_ids = [str(document["_id"]) for document in originals]
        edited_cursor = self.edited_collection.find(
            {"originalResumeId": {"$in": original_ids}},
            projection | {"originalResumeId": 1},
        ).sort("updatedAt", -1)

        latest_edits_by_original_id: dict[str, dict[str, Any]] = {}
        async for edited_document in edited_cursor:
            original_id = edited_document.get("originalResumeId")
            if original_id and original_id not in latest_edits_by_original_id:
                latest_edits_by_original_id[original_id] = edited_document

        return [
            serialize_resume_list_item(
                latest_edits_by_original_id.get(str(document["_id"]), document),
                stable_id=str(document["_id"]),
            )
            for document in originals
        ]

    async def get_latest_edited_copy(self, original_resume_id: str) -> dict[str, Any] | None:
        return await self.edited_collection.find_one(
            {"originalResumeId": original_resume_id},
            sort=[("updatedAt", -1), ("createdAt", -1)],
        )

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


def serialize_resume_list_item(document: dict[str, Any], stable_id: str | None = None) -> dict[str, Any]:
    candidate_profile = document.get("profile", {}).get("candidateProfile", {})
    metadata = document.get("metadata", {})

    return {
        "id": stable_id or str(document["_id"]),
        "filename": metadata.get("filename"),
        "candidateName": candidate_profile.get("fullName", ""),
        "candidateEmail": candidate_profile.get("email", ""),
        "currentTitle": candidate_profile.get("currentTitle", ""),
        "createdAt": serialize_datetime(document.get("createdAt")),
        "updatedAt": serialize_datetime(document.get("updatedAt")),
    }


def serialize_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)
