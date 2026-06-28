import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import Settings
from app.models.resume_schema import ResumeProfile, ResumeTemplateSaveRequest
from app.services.resume_preview import build_resume_preview_html

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
        self.template_collection_name = settings.mongodb_template_resume_collection
        self.template_collection: AsyncIOMotorCollection = self.client[self.database_name][self.template_collection_name]

    async def initialize(self) -> None:
        await self.client.admin.command("ping")
        await self.collection.create_index("createdAt")
        await self.collection.create_index("resumeId")
        await self.collection.create_index([("resumeId", 1), ("version", -1)])
        await self.collection.create_index("status")
        await self.collection.create_index("profile.data.email")
        await self.collection.create_index("metadata.filename")
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

    async def get_by_id(self, resume_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(resume_id):
            return None

        document = await self.get_latest_version(resume_id)
        if document is not None:
            return serialize_resume_document(document)

        legacy_document = await self.collection.find_one({"_id": ObjectId(resume_id)})
        return serialize_resume_document(legacy_document) if legacy_document is not None else None

    async def save_edited_copy(
        self,
        original_resume_id: str,
        profile: ResumeProfile,
        metadata: dict[str, Any],
        source: dict[str, Any],
    ) -> dict[str, Any]:
        if not ObjectId.is_valid(original_resume_id):
            raise ValueError("Original resume id is not valid.")

        latest_document = await self.get_latest_version(original_resume_id)
        if latest_document is None:
            latest_document = await self.collection.find_one({"_id": ObjectId(original_resume_id)})
        if latest_document is None:
            raise ValueError("Original resume was not found.")

        resume_id = latest_document.get("resumeId") or str(latest_document["_id"])
        next_version = int(latest_document.get("version") or 1) + 1
        now = datetime.now(UTC)
        document = {
            "resumeId": resume_id,
            "version": next_version,
            "status": "edited",
            "originalResumeId": original_resume_id,
            "profile": profile.model_dump(mode="json"),
            "metadata": {
                **metadata,
                "editedFromResumeId": original_resume_id,
                "version": next_version,
            },
            "source": {
                **source,
                "createdFrom": "ui-edit",
                "editedFromVersion": latest_document.get("version") or 1,
            },
            "createdAt": now,
            "updatedAt": now,
        }
        result = await self.collection.insert_one(document)
        saved_document = await self.collection.find_one({"_id": result.inserted_id})
        serialized_document = serialize_resume_document(saved_document or document | {"_id": result.inserted_id})
        serialized_document["previewHtml"] = build_resume_preview_html(profile)

        return serialized_document

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
        serialized_document = serialize_template_resume_document(saved_document or document | {"_id": result.inserted_id})
        serialized_document["previewHtml"] = build_resume_preview_html(template_resume)

        return serialized_document

    async def get_latest_template_resume(self, original_resume_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(original_resume_id):
            return None

        document = await self.template_collection.find_one(
            {"originalResumeId": original_resume_id},
            sort=[("updatedAt", -1), ("createdAt", -1)],
        )

        if document is not None:
            serialized_document = serialize_template_resume_document(document)
            serialized_document["previewHtml"] = build_resume_preview_html(
                ResumeTemplateSaveRequest.model_validate(serialized_document["templateResume"])
            )
            return serialized_document

        return None

    async def list_saved(self, limit: int = 100, skip: int = 0) -> list[dict[str, Any]]:
        projection = {
            "resumeId": 1,
            "version": 1,
            "status": 1,
            "metadata.filename": 1,
            "profile.data.name": 1,
            "profile.data.email": 1,
            "profile.data.title": 1,
            "createdAt": 1,
            "updatedAt": 1,
        }
        pipeline = [
            {"$addFields": {"effectiveResumeId": {"$ifNull": ["$resumeId", {"$toString": "$_id"}]}}},
            {"$sort": {"effectiveResumeId": 1, "version": -1, "updatedAt": -1, "createdAt": -1}},
            {"$group": {"_id": "$effectiveResumeId", "document": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$document"}},
            {"$sort": {"updatedAt": -1, "createdAt": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {"$project": projection},
        ]

        documents = [
            document
            async for document in self.collection.aggregate(pipeline)
        ]

        return [serialize_resume_list_item(document) for document in documents]

    async def get_latest_version(self, resume_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"resumeId": resume_id},
            sort=[("version", -1), ("updatedAt", -1), ("createdAt", -1)],
        )

    def close(self) -> None:
        self.client.close()


def serialize_resume_document(document: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(document)
    version_document_id = str(serialized.pop("_id"))
    resume_id = serialized.get("resumeId") or version_document_id
    serialized["resumeId"] = resume_id
    serialized["id"] = resume_id
    serialized.setdefault("version", 1)
    serialized.setdefault("status", "parsed")

    for key in ("createdAt", "updatedAt"):
        value = serialized.get(key)
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()

    return serialized


def serialize_template_resume_document(document: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(document)
    serialized["id"] = str(serialized.pop("_id"))

    for key in ("createdAt", "updatedAt"):
        serialized[key] = serialize_datetime(serialized.get(key))

    return serialized


def serialize_resume_list_item(document: dict[str, Any], stable_id: str | None = None) -> dict[str, Any]:
    profile_data = document.get("profile", {}).get("data", {})
    metadata = document.get("metadata", {})
    resume_id = stable_id or document.get("resumeId") or document.get("effectiveResumeId") or str(document["_id"])

    return {
        "id": resume_id,
        "filename": metadata.get("filename"),
        "candidateName": profile_data.get("name", ""),
        "candidateEmail": profile_data.get("email", ""),
        "currentTitle": profile_data.get("title", ""),
        "createdAt": serialize_datetime(document.get("createdAt")),
        "updatedAt": serialize_datetime(document.get("updatedAt")),
    }


def serialize_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)
