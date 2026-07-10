from __future__ import annotations

import logging
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import Settings
from app.models.resume_schema import ResumeProfile
from app.services.ats_score_service import calculate_ats_score
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
        original = await self._find_original(resume_id, user_id=user_id)
        if original is None:
            return None

        stable_resume_id = self._stable_resume_id(original)
        edited_resume = self._edited_resume_snapshot(original)
        if edited_resume is not None:
            return self._to_response_document(edited_resume, original=original, stable_resume_id=stable_resume_id)

        return self._to_response_document(original, stable_resume_id=stable_resume_id)

    async def get_resume_by_id(
        self,
        resume_id: str,
        source: str,
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        user_id = self._normalize_user_id(user_id)
        normalized_source = source.strip().casefold()
        if normalized_source == "parsed":
            return await self._find_resume_document(self.collection, resume_id, user_id=user_id)
        if normalized_source == "edited":
            original = await self._find_resume_document(self.collection, resume_id, user_id=user_id)
            if original is None:
                return None

            return self._edited_resume_snapshot(original) or original

        raise ValueError("source must be either 'parsed' or 'edited'.")

    async def get_parsed_and_edited_resume(
        self,
        resume_id: str,
        user_id: str | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        user_id = self._normalize_user_id(user_id)
        parsed_resume = await self.get_resume_by_id(resume_id, "parsed", user_id=user_id)
        edited_resume = self._edited_resume_snapshot(parsed_resume) if parsed_resume is not None else None

        return parsed_resume, edited_resume

    async def save_edited(
        self,
        resume_id: str,
        profile: ResumeProfile,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        user_id = self._normalize_user_id(user_id)
        original = await self._find_original(resume_id, user_id=user_id)
        if original is None:
            raise ResumeNotFoundError(f"Resume {resume_id!r} was not found.")

        stable_resume_id = self._stable_resume_id(original)
        owner_user_id = self._document_user_id(original)
        now = datetime.now(UTC)
        metadata = original.get("metadata") or {}
        source = original.get("source") or {}
        existing_edit = self._edited_resume_snapshot(original) or {}
        avatar = existing_edit.get("avatar") or original.get("avatar") or ""
        with_photo = bool(existing_edit.get("withPhoto") or original.get("withPhoto") or avatar)
        profile_document = profile.model_dump(mode="json")
        ats_calculation = calculate_ats_score(profile_document)

        edited_resume = {
            "resumeId": stable_resume_id,
            "version": 1,
            "status": "edited",
            "avatar": avatar,
            "withPhoto": with_photo,
            "profile": profile_document,
            "metadata": metadata,
            "source": {
                "jobDescription": source.get("jobDescription"),
                "createdFrom": "edit",
                "originalResumeId": stable_resume_id,
            },
            **self._ats_storage_fields(ats_calculation, calculated_at=now),
            "createdAt": existing_edit.get("createdAt") or now,
            "updatedAt": now,
        }
        if owner_user_id:
            edited_resume["userId"] = owner_user_id

        await self.collection.update_one(
            {"_id": original["_id"]},
            {"$set": {"editedResume": edited_resume, "updatedAt": now}},
        )

        logger.info(
            "Saved edited resume snapshot to MongoDB database=%r collection=%r resume_id=%s user_id=%s",
            self.database_name,
            self.collection_name,
            stable_resume_id,
            owner_user_id,
        )
        return self._to_response_document(edited_resume, original=original, stable_resume_id=stable_resume_id)

    async def save_ats_calculation(
        self,
        resume_id: str,
        calculation: dict[str, Any],
        user_id: str | None = None,
    ) -> bool:
        """Store an ATS calculation on an embedded edited resume snapshot."""
        user_id = self._normalize_user_id(user_id)
        original = await self._find_original(resume_id, user_id=user_id)
        if original is None or self._edited_resume_snapshot(original) is None:
            return False

        now = datetime.now(UTC)
        ats_fields = self._ats_storage_fields(calculation, calculated_at=now)
        update_fields = {
            f"editedResume.{field_name}": value
            for field_name, value in ats_fields.items()
        }
        update_fields["editedResume.updatedAt"] = now
        update_fields["updatedAt"] = now
        result = await self.collection.update_one(
            {"_id": original["_id"]},
            {
                "$set": update_fields,
            },
        )
        stored = bool(getattr(result, "matched_count", 0))
        if stored:
            logger.info(
                "Saved ATS calculation to MongoDB database=%r collection=%r resume_id=%s user_id=%s",
                self.database_name,
                self.collection_name,
                self._stable_resume_id(original),
                user_id,
            )
        return stored

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

        if self._edited_resume_snapshot(original) is not None:
            image_update.update(
                {
                    "editedResume.avatar": image_url,
                    "editedResume.withPhoto": True,
                    "editedResume.image": image_metadata,
                    "editedResume.updatedAt": now,
                }
            )

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

    async def _find_resume_document(
        self,
        collection: AsyncIOMotorCollection,
        resume_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        normalized_resume_id = str(resume_id).strip()
        if not normalized_resume_id:
            return None

        filters: list[dict[str, Any]] = [
            {"resumeId": normalized_resume_id},
            {"id": normalized_resume_id},
        ]
        if ObjectId.is_valid(normalized_resume_id):
            filters.append({"_id": ObjectId(normalized_resume_id)})

        id_filter: dict[str, Any] = {"$or": filters}
        user_id = self._normalize_user_id(user_id)
        query = {"$and": [id_filter, {"userId": user_id}]} if user_id else id_filter
        return await collection.find_one(query)

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

    @staticmethod
    def _edited_resume_snapshot(document: dict[str, Any]) -> dict[str, Any] | None:
        edited_resume = document.get("editedResume")
        if isinstance(edited_resume, dict) and edited_resume.get("profile"):
            return edited_resume
        return None

    @staticmethod
    def _ats_storage_fields(
        calculation: dict[str, Any],
        *,
        calculated_at: datetime,
    ) -> dict[str, Any]:
        if not isinstance(calculation, dict):
            raise TypeError("ATS calculation must be a dictionary.")

        score = calculation.get("atsScore")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("ATS calculation must include a numeric atsScore.")

        numeric_score = int(score)
        if numeric_score < 0 or numeric_score > 100:
            raise ValueError("ATS calculation atsScore must be between 0 and 100.")

        stored_calculation = deepcopy(calculation)
        stored_calculation["atsScore"] = numeric_score
        return {
            "atsScore": numeric_score,
            "atsCalculation": stored_calculation,
            "atsCalculatedAt": calculated_at,
        }

    @classmethod
    def _to_response_document(
        cls,
        document: dict[str, Any],
        *,
        original: dict[str, Any] | None = None,
        stable_resume_id: str | None = None,
    ) -> dict[str, Any]:
        resume_id = stable_resume_id or cls._stable_resume_id(document)
        metadata = document.get("metadata")
        if metadata is None and original is not None:
            metadata = original.get("metadata")
        user_id = cls._document_user_id(document)
        if user_id is None and original is not None:
            user_id = cls._document_user_id(original)
        avatar = document.get("avatar")
        if avatar is None and original is not None:
            avatar = original.get("avatar")
        avatar = str(avatar or "")

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
