from __future__ import annotations

import logging
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import Settings
from app.models.resume_schema import ResumeProfile
from app.services.resume_parser import normalize_resume_profile_payload

logger = logging.getLogger(__name__)


class ResumeRepositoryNotConfiguredError(RuntimeError):
    pass


class ResumeNotFoundError(LookupError):
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
        await self.collection.create_index("userId")
        await self.collection.create_index([("userId", 1), ("createdAt", -1)])
        await self.collection.create_index("profile.data.email")
        await self.collection.create_index("metadata.filename")

    async def save(
        self,
        profile: ResumeProfile,
        metadata: dict[str, Any],
        job_description: str | None,
        user_id: str | None = None,
    ) -> str:
        user_id = self._normalize_user_id(user_id)
        now = datetime.now(UTC)
        resume_object_id = ObjectId()
        resume_id = str(resume_object_id)
        document = {
            "_id": resume_object_id,
            "resumeId": resume_id,
            "version": 1,
            "status": "parsed",
            "avatar": "",
            "withPhoto": False,
            "profile": profile.model_dump(mode="json"),
            "metadata": metadata,
            "source": {
                "jobDescription": job_description,
                "createdFrom": "parse",
            },
            "createdAt": now,
            "updatedAt": now,
        }
        if user_id:
            document["userId"] = user_id

        result = await self.collection.insert_one(document)
        logger.info(
            "Saved parsed resume to MongoDB database=%r collection=%r resume_id=%s user_id=%s inserted_id=%s",
            self.database_name,
            self.collection_name,
            resume_id,
            user_id,
            result.inserted_id,
        )
        return str(result.inserted_id)

    async def list(self, limit: int, skip: int, user_id: str | None = None) -> list[dict[str, Any]]:
        user_id = self._normalize_user_id(user_id)
        filter_document: dict[str, Any] = {"userId": user_id} if user_id else {}
        cursor = self.collection.find(filter_document).sort("createdAt", -1).skip(skip).limit(limit)
        documents = await cursor.to_list(length=limit)
        return [self._to_response_document(document) for document in documents]

    async def get(self, resume_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        user_id = self._normalize_user_id(user_id)
        document = await self._find_original(resume_id, user_id=user_id)
        if document is None:
            return None

        return self._to_response_document(document)

    async def save_image(
        self,
        resume_id: str,
        image_url: str,
        image_metadata: dict[str, Any],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        user_id = self._normalize_user_id(user_id)
        original = await self._find_original(resume_id, user_id=user_id)
        if original is None:
            raise ResumeNotFoundError(f"Resume {resume_id!r} was not found.")

        stable_resume_id = self._stable_resume_id(original)
        owner_user_id = self._document_user_id(original)
        now = datetime.now(UTC)
        image_update = {
            "avatar": image_url,
            "withPhoto": True,
            "image": image_metadata,
            "updatedAt": now,
        }
        if owner_user_id:
            image_update["userId"] = owner_user_id

        await self.collection.update_one({"_id": original["_id"]}, {"$set": image_update})

        updated = await self.get(stable_resume_id, user_id=owner_user_id)
        if updated is None:
            raise RuntimeError("Resume image was saved but the resume document could not be read.")

        logger.info(
            "Saved resume image URL to MongoDB database=%r resume_id=%s user_id=%s",
            self.database_name,
            stable_resume_id,
            owner_user_id,
        )
        return updated

    async def _find_original(self, resume_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        user_id = self._normalize_user_id(user_id)
        filters: list[dict[str, Any]] = [{"resumeId": resume_id}]
        if ObjectId.is_valid(resume_id):
            filters.append({"_id": ObjectId(resume_id)})

        id_filter: dict[str, Any] = {"$or": filters}
        if user_id:
            return await self.collection.find_one({"$and": [id_filter, {"userId": user_id}]})

        return await self.collection.find_one(id_filter)

    @staticmethod
    def _stable_resume_id(document: dict[str, Any]) -> str:
        resume_id = document.get("resumeId") or document.get("id")
        if resume_id:
            return str(resume_id)
        return str(document["_id"])

    @staticmethod
    def _normalize_user_id(user_id: Any) -> str | None:
        if user_id is None:
            return None

        normalized = str(user_id).strip()
        return normalized or None

    @staticmethod
    def _document_user_id(document: dict[str, Any]) -> str | None:
        return MongoResumeRepository._normalize_user_id(document.get("userId"))

    @classmethod
    def _to_response_document(
        cls,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        resume_id = cls._stable_resume_id(document)
        metadata = document.get("metadata")
        user_id = cls._document_user_id(document)
        avatar = str(document.get("avatar") or "")

        profile = document.get("profile", {})
        if isinstance(profile, dict):
            normalized_profile = normalize_resume_profile_payload(deepcopy(profile))
            if isinstance(normalized_profile, dict):
                profile = normalized_profile

        return {
            "id": resume_id,
            "resumeId": resume_id,
            "userId": user_id,
            "version": document.get("version"),
            "status": document.get("status"),
            "avatar": avatar,
            "withPhoto": bool(document.get("withPhoto") or avatar),
            "profile": profile,
            "metadata": metadata or {},
        }

    def close(self) -> None:
        self.client.close()
