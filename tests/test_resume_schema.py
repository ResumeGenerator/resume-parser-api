from io import BytesIO
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.main import app
from app.api.routes_resume import get_resume_image_storage
from app.core.config import Settings, get_settings
from app.core.llm_client import OpenAIClient, get_llm_client
from app.models.resume_schema import ResumeProfile, ResumeRephraseRequest
from app.services.resume_image_storage import LocalResumeImageStorage
from app.services.resume_rephraser import ResumeRephraseService
from app.services.resume_parser import normalize_resume_profile_payload, split_summary_items
from app.services.resume_repository import MongoResumeRepository
from app.utils.text_cleaner import clean_resume_text


class ResumeSchemaTests(unittest.TestCase):
    def test_service_payload_normalizer_unwraps_profile_payload(self) -> None:
        payload = {
            "profile": {
                "data": {"name": "Biju Manayagaths", "sections": []},
            }
        }

        normalized = normalize_resume_profile_payload(payload)

        self.assertEqual(normalized["data"]["name"], "Biju Manayagaths")

    def test_service_payload_normalizer_splits_summary_section_items(self) -> None:
        payload = {
            "data": {
                "sections": [
                    {
                        "title": "Professional summary",
                        "type": "summary",
                        "items": (
                            "- Strategic and results-driven Senior Software Engineer.\n"
                            "- Proven expertise in end-to-end solution architecture.\n"
                            "- Strong background in back-end and API-driven architectures."
                        ),
                    }
                ]
            }
        }

        normalized = normalize_resume_profile_payload(payload)

        self.assertEqual(
            normalized["data"]["sections"][0]["items"],
            [
                "Strategic and results-driven Senior Software Engineer.",
                "Proven expertise in end-to-end solution architecture.",
                "Strong background in back-end and API-driven architectures.",
            ],
        )

    def test_service_payload_normalizer_splits_education_field_of_study_from_degree(self) -> None:
        payload = {
            "data": {
                "sections": [
                    {
                        "title": "Education",
                        "type": "education",
                        "items": [
                            {
                                "degree": "Master of Computer Application (Computers)",
                                "school": "PSG College",
                                "field_of_study": "",
                            }
                        ],
                    }
                ]
            }
        }

        normalized = normalize_resume_profile_payload(payload)
        education_item = normalized["data"]["sections"][0]["items"][0]
        profile = ResumeProfile.model_validate(normalized)

        self.assertEqual(education_item["degree"], "Master of Computer Application")
        self.assertEqual(education_item["fieldOfStudy"], "Computers")
        self.assertNotIn("field_of_study", education_item)
        self.assertEqual(profile.data.sections[0].items[0].fieldOfStudy, "Computers")

    def test_service_payload_normalizer_converts_skill_text_to_items(self) -> None:
        payload = {
            "data": {
                "sections": [
                    {
                        "title": "Skills",
                        "type": "skill",
                        "items": [
                            "Technical Skills: Python, FastAPI; Docker",
                            "Cloud: AWS",
                            {"skill": "MongoDB", "aiGenerated": True},
                            {"name": "python", "suggested": True},
                        ],
                    }
                ]
            }
        }

        normalized = normalize_resume_profile_payload(payload)
        skill_items = normalized["data"]["sections"][0]["items"]
        profile = ResumeProfile.model_validate(normalized)

        self.assertEqual(
            skill_items,
            [
                {"name": "Python", "aiGenerated": False},
                {"name": "FastAPI", "aiGenerated": False},
                {"name": "Docker", "aiGenerated": False},
                {"name": "AWS", "aiGenerated": False},
                {"name": "MongoDB", "aiGenerated": True},
            ],
        )
        self.assertEqual(profile.data.sections[0].items[0].name, "Python")
        self.assertFalse(profile.data.sections[0].items[0].aiGenerated)

    def test_resume_profile_converts_legacy_skill_level_to_ai_generated_default(self) -> None:
        profile = ResumeProfile.model_validate(
            {
                "data": {
                    "sections": [
                        {
                            "title": "Skills",
                            "type": "skill",
                            "items": [
                                {"name": "Python", "level": "Expert"},
                            ],
                        }
                    ]
                }
            }
        )

        skill_item = profile.data.sections[0].items[0]
        self.assertEqual(skill_item.model_dump(mode="json"), {"name": "Python", "aiGenerated": False})

    def test_split_summary_items_uses_visible_delimiters(self) -> None:
        items = split_summary_items(
            "PROFILE SUMMARY\n"
            "❖ Strategic and results-driven Senior Software Engineer.\n"
            "❖ Proven expertise in end-to-end solution architecture."
        )

        self.assertEqual(
            items,
            [
                "Strategic and results-driven Senior Software Engineer.",
                "Proven expertise in end-to-end solution architecture.",
            ],
        )

    def test_clean_resume_text_normalizes_diamond_summary_bullets(self) -> None:
        text = clean_resume_text("PROFILE SUMMARY\n❖ Strategic engineer\n◆ Cloud architect")

        self.assertEqual(text, "PROFILE SUMMARY\n- Strategic engineer\n- Cloud architect")

    def test_resume_profile_defaults_to_resume_data_only(self) -> None:
        profile = ResumeProfile.model_validate({"data": {"sections": []}})

        self.assertEqual(set(profile.model_dump(mode="json")), {"data"})
        self.assertFalse(hasattr(profile, "template"))

    def test_resume_profile_accepts_parser_data_shape(self) -> None:
        payload = {
            "data": {
                "name": "Biju Manayagaths",
                "title": "Solution Architect s",
                "location": "Doha,   Doha, Qatar,",
                "phone": "+97474452435",
                "email": "bijum777@gmail.com",
                "summary": "Senior Engineer with expertise in designing scalable system architectures.",
                "dateOfBirth": "",
                "gender": "",
                "nationality": "",
                "documentDate": "",
                "address": "",
                "postalCode": "",
                "secondaryAddress": None,
                "sections": [
                    {
                        "title": "Professional summary",
                        "type": "summary",
                        "items": "Senior Engineer with expertise in designing scalable system architectures.",
                    },
                    {
                        "title": "Work experience",
                        "type": "experience",
                        "items": [
                            {
                                "position": "Senior Engineer",
                                "company": "Lexis Nexis",
                                "location": "London",
                                "jobType": "",
                                "reasonForLeaving": "",
                                "start": "Apr 2026",
                                "end": "May 2026",
                                "achievements": [
                                    "Designed and implemented scalable system architectures.",
                                ],
                            }
                        ],
                    },
                    {
                        "title": "Skills",
                        "type": "skill",
                        "items": [
                            {"name": "Development", "aiGenerated": False},
                            {"name": "Cloud computing", "aiGenerated": True},
                        ],
                    },
                ],
            },
        }

        profile = ResumeProfile.model_validate(payload)

        self.assertEqual(profile.data.email, "bijum777@gmail.com")
        self.assertEqual(profile.data.sections[0].items, payload["data"]["sections"][0]["items"])
        self.assertEqual(profile.data.sections[1].items[0].company, "Lexis Nexis")

    def test_resume_profile_accepts_education_field_of_study(self) -> None:
        profile = ResumeProfile.model_validate(
            {
                "data": {
                    "sections": [
                        {
                            "title": "Education",
                            "type": "education",
                            "items": [
                                {
                                    "degree": "Bachelor of Science",
                                    "fieldOfStudy": "Computer Science",
                                    "school": "Example University",
                                    "faculty": "",
                                    "department": "",
                                    "location": "",
                                    "years": "2018",
                                    "start": "",
                                    "end": "",
                                    "highlights": [],
                                }
                            ],
                        }
                    ]
                }
            }
        )

        education_item = profile.data.sections[0].items[0]
        self.assertEqual(education_item.degree, "Bachelor of Science")
        self.assertEqual(education_item.fieldOfStudy, "Computer Science")

    def test_work_experience_dates_normalize_to_day_month_year(self) -> None:
        profile = ResumeProfile.model_validate(
            {
                "data": {
                    "sections": [
                        {
                            "title": "Work experience",
                            "type": "experience",
                            "items": [
                                {
                                    "position": "Senior Engineer",
                                    "company": "Example Co",
                                    "location": "",
                                    "jobType": "",
                                    "reasonForLeaving": "",
                                    "start": "Dec 22",
                                    "end": "June 23, 2026",
                                    "achievements": [],
                                },
                                {
                                    "position": "Lead Engineer",
                                    "company": "Current Co",
                                    "location": "",
                                    "jobType": "",
                                    "reasonForLeaving": "",
                                    "start": "2024",
                                    "end": "current",
                                    "achievements": [],
                                },
                            ],
                        }
                    ]
                }
            }
        )

        first_experience = profile.data.sections[0].items[0]
        second_experience = profile.data.sections[0].items[1]
        self.assertEqual(first_experience.start, "01-12-2022")
        self.assertEqual(first_experience.end, "23-06-2026")
        self.assertEqual(second_experience.start, "01-01-2024")
        self.assertEqual(second_experience.end, "Present")

    def test_resume_profile_forbids_template_presentation_fields(self) -> None:
        payload = {
            "data": {"sections": []},
            "template": "professional-dark-blue",
            "format": "html",
            "font": "Arial",
            "color": "#000000",
            "withPhoto": True,
            "avatar": "https://example.com/avatar.png",
            "contactsTitle": "Contacts",
            "detailsTitle": "Details",
        }

        with self.assertRaises(ValidationError):
            ResumeProfile.model_validate(payload)


class ResumeRephraseTests(unittest.IsolatedAsyncioTestCase):
    def test_rephrase_request_strips_text(self) -> None:
        request = ResumeRephraseRequest.model_validate({"text": "  built APIs  "})

        self.assertEqual(request.text, "built APIs")

    def test_rephrase_request_accepts_legacy_prompt_field(self) -> None:
        request = ResumeRephraseRequest.model_validate(
            {
                "text": "built APIs",
                "prompt": "Improve only resume-related text.",
            }
        )

        self.assertEqual(request.text, "built APIs")
        self.assertEqual(request.prompt, "Improve only resume-related text.")

    def test_rephrase_request_rejects_blank_text(self) -> None:
        with self.assertRaises(ValidationError):
            ResumeRephraseRequest.model_validate({"text": "   "})

    async def test_rephrase_service_validates_strict_response_schema(self) -> None:
        fake_client = unittest.mock.Mock()
        fake_client.rephrase_resume_text = AsyncMock(
            return_value={"rephrasedText": "Built and maintained REST APIs.", "extra": "not allowed"}
        )

        with self.assertRaises(HTTPException) as error:
            await ResumeRephraseService(fake_client).rephrase("built APIs")

        self.assertEqual(error.exception.status_code, 502)

    async def test_rephrase_service_rejects_non_resume_commentary(self) -> None:
        fake_client = unittest.mock.Mock()
        fake_client.rephrase_resume_text = AsyncMock(
            return_value={"rephrasedText": "Here is a professional version: Built REST APIs."}
        )

        with self.assertRaises(HTTPException) as error:
            await ResumeRephraseService(fake_client).rephrase("built APIs")

        self.assertEqual(error.exception.status_code, 502)

    async def test_rephrase_service_preserves_line_separated_text_blocks(self) -> None:
        fake_client = unittest.mock.Mock()
        fake_client.rephrase_resume_text = AsyncMock(
            side_effect=[
                {"rephrasedText": "Built and maintained REST APIs."},
                {"rephrasedText": "Resolved production defects across backend services."},
            ]
        )

        response = await ResumeRephraseService(fake_client).rephrase("built APIs\n\nfixed production bugs")

        self.assertEqual(
            response.rephrasedText,
            "Built and maintained REST APIs.\n\nResolved production defects across backend services.",
        )
        self.assertEqual(
            fake_client.rephrase_resume_text.await_args_list,
            [unittest.mock.call("built APIs"), unittest.mock.call("fixed production bugs")],
        )

    def test_rephrase_endpoint_returns_validated_response(self) -> None:
        fake_client = unittest.mock.Mock()
        fake_client.rephrase_resume_text = AsyncMock(
            return_value={"rephrasedText": "Built and maintained scalable REST APIs."}
        )

        with patch("app.api.routes_resume.get_llm_client", return_value=fake_client):
            response = TestClient(app).post(
                "/api/resumes/rephrase",
                json={
                    "text": "built APIs",
                    "prompt": "Improve only resume-related text.",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"rephrasedText": "Built and maintained scalable REST APIs."})
        fake_client.rephrase_resume_text.assert_awaited_once_with("built APIs")

    def test_rephrase_endpoint_accepts_json_with_unescaped_newline(self) -> None:
        fake_client = unittest.mock.Mock()
        fake_client.rephrase_resume_text = AsyncMock(
            side_effect=[
                {"rephrasedText": "Built and maintained APIs."},
                {"rephrasedText": "Resolved production issues."},
            ]
        )
        raw_body = '{"text":"built APIs\nfixed production bugs"}'

        with patch("app.api.routes_resume.get_llm_client", return_value=fake_client):
            response = TestClient(app).post(
                "/api/resumes/rephrase",
                content=raw_body,
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"rephrasedText": "Built and maintained APIs.\nResolved production issues."},
        )
        self.assertEqual(
            fake_client.rephrase_resume_text.await_args_list,
            [unittest.mock.call("built APIs"), unittest.mock.call("fixed production bugs")],
        )

    def test_rephrase_endpoint_accepts_text_plain(self) -> None:
        fake_client = unittest.mock.Mock()
        fake_client.rephrase_resume_text = AsyncMock(
            side_effect=[
                {"rephrasedText": "Built and maintained APIs."},
                {"rephrasedText": "Resolved production issues."},
            ]
        )

        with patch("app.api.routes_resume.get_llm_client", return_value=fake_client):
            response = TestClient(app).post(
                "/api/resumes/rephrase",
                content="built APIs\nfixed production bugs",
                headers={"Content-Type": "text/plain"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"rephrasedText": "Built and maintained APIs.\nResolved production issues."},
        )
        self.assertEqual(
            fake_client.rephrase_resume_text.await_args_list,
            [unittest.mock.call("built APIs"), unittest.mock.call("fixed production bugs")],
        )

    def test_rephrase_endpoint_rejects_malformed_json_with_helpful_message(self) -> None:
        response = TestClient(app).post(
            "/api/resumes/rephrase",
            content='{"text":"built APIs"',
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("JSON object", response.json()["detail"]["message"])


class MongoResumeRepositoryTests(unittest.IsolatedAsyncioTestCase):
    def test_response_document_normalizes_legacy_skill_level(self) -> None:
        resume_id = ObjectId()
        document = {
            "_id": resume_id,
            "resumeId": str(resume_id),
            "version": 1,
            "status": "parsed",
            "profile": {
                "data": {
                    "name": "Alex Morgan",
                    "sections": [
                        {
                            "title": "Skills",
                            "type": "skill",
                            "items": [{"name": "Python", "level": "Expert"}],
                        }
                    ],
                }
            },
            "metadata": {"filename": "alex.pdf"},
        }

        response_document = MongoResumeRepository._to_response_document(document)

        self.assertEqual(
            response_document["profile"]["data"]["sections"][0]["items"],
            [{"name": "Python", "aiGenerated": False}],
        )

    async def test_save_stores_parsed_resume_document(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.database_name = "resume_parser"
        repository.collection_name = "parsed_resumes"
        repository.collection = unittest.mock.Mock()

        async def insert_one(document: dict) -> unittest.mock.Mock:
            return unittest.mock.Mock(inserted_id=document["_id"])

        repository.collection.insert_one = AsyncMock(side_effect=insert_one)

        profile = ResumeProfile.model_validate(
            {
                "data": {
                    "name": "Alex Morgan",
                    "email": "alex@example.com",
                    "sections": [],
                }
            }
        )

        resume_id = await repository.save(
            profile=profile,
            metadata={"filename": "alex.pdf"},
            job_description="Python backend engineer",
            user_id="user-123",
        )

        self.assertTrue(ObjectId.is_valid(resume_id))
        repository.collection.insert_one.assert_awaited_once()
        saved_document = repository.collection.insert_one.await_args.args[0]
        self.assertEqual(resume_id, str(saved_document["_id"]))
        self.assertEqual(saved_document["resumeId"], str(saved_document["_id"]))
        self.assertEqual(saved_document["userId"], "user-123")
        self.assertEqual(saved_document["version"], 1)
        self.assertEqual(saved_document["status"], "parsed")
        self.assertEqual(saved_document["profile"]["data"]["name"], "Alex Morgan")
        self.assertEqual(saved_document["source"]["createdFrom"], "parse")

    async def test_list_filters_parsed_resumes_by_user_id(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.collection = unittest.mock.Mock()

        class FakeCursor:
            def sort(self, *args: object, **kwargs: object) -> "FakeCursor":
                return self

            def skip(self, *args: object, **kwargs: object) -> "FakeCursor":
                return self

            def limit(self, *args: object, **kwargs: object) -> "FakeCursor":
                return self

            async def to_list(self, length: int) -> list[dict]:
                return [
                    {
                        "_id": ObjectId(),
                        "resumeId": "resume123",
                        "userId": "user-123",
                        "version": 1,
                        "status": "parsed",
                        "profile": {"data": {"name": "Alex Morgan", "sections": []}},
                        "metadata": {"filename": "alex.pdf"},
                    }
                ]

        repository.collection.find = unittest.mock.Mock(return_value=FakeCursor())

        documents = await repository.list(limit=10, skip=5, user_id="user-123")

        repository.collection.find.assert_called_once_with({"userId": "user-123"})
        self.assertEqual(documents[0]["userId"], "user-123")

    async def test_find_original_filters_by_user_id_when_provided(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.collection = unittest.mock.Mock()
        repository.collection.find_one = AsyncMock(return_value=None)
        resume_id = str(ObjectId())

        await repository._find_original(resume_id, user_id="user-123")

        repository.collection.find_one.assert_awaited_once_with(
            {
                "$and": [
                    {"$or": [{"resumeId": resume_id}, {"_id": ObjectId(resume_id)}]},
                    {"userId": "user-123"},
                ]
            }
        )

    async def test_save_edited_upserts_single_record_per_resume(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.database_name = "resume_parser"
        repository.collection_name = "parsed_resumes"
        repository.edited_collection_name = "edited_resumes"
        repository.collection = unittest.mock.Mock()
        repository.edited_collection = unittest.mock.Mock()

        original_id = ObjectId()
        original_document = {
            "_id": original_id,
            "resumeId": str(original_id),
            "version": 1,
            "status": "parsed",
            "profile": {"data": {"name": "Alex Morgan", "sections": []}},
            "metadata": {"filename": "alex.pdf"},
            "source": {"jobDescription": "Python backend engineer"},
        }
        edited_document: dict | None = None

        async def update_one(filter_document: dict, update_document: dict, upsert: bool = False) -> unittest.mock.Mock:
            nonlocal edited_document
            edited_document = {
                **update_document["$setOnInsert"],
                **update_document["$set"],
            }
            return unittest.mock.Mock(matched_count=0, modified_count=0, upserted_id=edited_document["_id"])

        async def find_edited(*args: object, **kwargs: object) -> dict:
            self.assertIsNotNone(edited_document)
            return edited_document

        repository.collection.find_one = AsyncMock(return_value=original_document)
        repository.edited_collection.update_one = AsyncMock(side_effect=update_one)
        repository.edited_collection.find_one = AsyncMock(side_effect=find_edited)

        profile = ResumeProfile.model_validate(
            {
                "data": {
                    "name": "Alex Morgan",
                    "title": "Principal Engineer",
                    "sections": [],
                }
            }
        )

        saved_document = await repository.save_edited(str(original_id), profile)

        repository.edited_collection.update_one.assert_awaited_once()
        filter_document = repository.edited_collection.update_one.await_args.args[0]
        update_document = repository.edited_collection.update_one.await_args.args[1]
        self.assertEqual(filter_document, {"resumeId": str(original_id)})
        self.assertTrue(repository.edited_collection.update_one.await_args.kwargs["upsert"])
        self.assertEqual(update_document["$set"]["version"], 1)
        self.assertEqual(update_document["$set"]["status"], "edited")
        self.assertEqual(update_document["$set"]["avatar"], "")
        self.assertFalse(update_document["$set"]["withPhoto"])
        self.assertEqual(saved_document["id"], str(original_id))
        self.assertEqual(saved_document["resumeId"], str(original_id))
        self.assertEqual(saved_document["version"], 1)
        self.assertEqual(saved_document["status"], "edited")
        self.assertEqual(saved_document["metadata"], {"filename": "alex.pdf"})
        self.assertEqual(saved_document["profile"]["data"]["title"], "Principal Engineer")

    async def test_save_image_updates_original_and_edited_resume_documents(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.database_name = "resume_parser"
        repository.collection = unittest.mock.Mock()
        repository.edited_collection = unittest.mock.Mock()

        original_id = ObjectId()
        resume_id = str(original_id)
        original_document = {
            "_id": original_id,
            "resumeId": resume_id,
            "version": 1,
            "status": "parsed",
            "profile": {"data": {"name": "Alex Morgan", "sections": []}},
            "metadata": {"filename": "alex.pdf"},
        }
        updated_document = {
            **original_document,
            "avatar": "https://api.example.com/api/resumes/images/avatar.png",
            "withPhoto": True,
            "image": {"filename": "avatar.png"},
        }

        repository.collection.find_one = AsyncMock(side_effect=[original_document, updated_document])
        repository.collection.update_one = AsyncMock(return_value=unittest.mock.Mock(modified_count=1))
        repository.edited_collection.update_one = AsyncMock(return_value=unittest.mock.Mock(modified_count=0))
        repository.edited_collection.find_one = AsyncMock(return_value=None)

        response_document = await repository.save_image(
            resume_id,
            "https://api.example.com/api/resumes/images/avatar.png",
            {"filename": "avatar.png"},
        )

        repository.collection.update_one.assert_awaited_once()
        collection_filter, collection_update = repository.collection.update_one.await_args.args
        self.assertEqual(collection_filter, {"_id": original_id})
        self.assertEqual(collection_update["$set"]["avatar"], "https://api.example.com/api/resumes/images/avatar.png")
        self.assertTrue(collection_update["$set"]["withPhoto"])
        repository.edited_collection.update_one.assert_awaited_once_with(
            {"resumeId": resume_id},
            {"$set": collection_update["$set"]},
        )
        self.assertEqual(response_document["avatar"], "https://api.example.com/api/resumes/images/avatar.png")
        self.assertTrue(response_document["withPhoto"])


class ResumeUserIdEndpointTests(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_parse_endpoint_forwards_user_id_to_repository(self) -> None:
        class FakeLLMClient:
            async def extract_resume_profile(self, resume_text: str, job_description: str | None) -> dict:
                return {
                    "data": {
                        "name": "Alex Morgan",
                        "email": "alex@example.com",
                        "sections": [],
                    }
                }

        class FakeRepository:
            def __init__(self) -> None:
                self.saved_user_id: str | None = None

            async def save(
                self,
                profile: ResumeProfile,
                metadata: dict,
                job_description: str | None,
                user_id: str | None = None,
            ) -> str:
                self.saved_user_id = user_id
                return "resume123"

        resume_text = (
            "Alex Morgan\n"
            "alex@example.com\n"
            "+1 555 0100\n"
            "Professional Summary\n"
            "Backend engineer building APIs.\n"
            "Work Experience\n"
            "Software Engineer 2020 - Present\n"
            "Education\n"
            "Skills\n"
            "Python, FastAPI\n"
        )
        fake_repository = FakeRepository()

        with (
            patch("app.api.routes_resume.get_llm_client", return_value=FakeLLMClient()),
            patch("app.api.routes_resume.get_resume_repository", return_value=fake_repository),
        ):
            response = TestClient(app).post(
                "/api/resumes/parse",
                data={"userId": " user-123 "},
                files={"file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_repository.saved_user_id, "user-123")
        self.assertEqual(response.json()["userId"], "user-123")

    def test_get_endpoint_forwards_user_id_to_repository(self) -> None:
        class FakeRepository:
            def __init__(self) -> None:
                self.requested_user_id: str | None = None

            async def get(self, resume_id: str, user_id: str | None = None) -> dict:
                self.requested_user_id = user_id
                return {
                    "id": resume_id,
                    "resumeId": resume_id,
                    "userId": user_id,
                    "version": 1,
                    "status": "parsed",
                    "profile": {"data": {"name": "Alex Morgan", "sections": []}},
                    "metadata": {"filename": "alex.pdf"},
                    "avatar": "",
                    "withPhoto": False,
                }

        fake_repository = FakeRepository()

        with patch("app.api.routes_resume.get_resume_repository", return_value=fake_repository):
            response = TestClient(app).get("/api/resumes/resume123?userId=user-123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_repository.requested_user_id, "user-123")
        self.assertEqual(response.json()["userId"], "user-123")

    def test_list_endpoint_forwards_user_id_to_repository(self) -> None:
        class FakeRepository:
            def __init__(self) -> None:
                self.requested_user_id: str | None = None

            async def list(self, limit: int, skip: int, user_id: str | None = None) -> list[dict]:
                self.requested_user_id = user_id
                return [
                    {
                        "id": "resume123",
                        "resumeId": "resume123",
                        "userId": user_id,
                        "version": 1,
                        "status": "parsed",
                        "profile": {"data": {"name": "Alex Morgan", "sections": []}},
                        "metadata": {"filename": "alex.pdf"},
                        "avatar": "",
                        "withPhoto": False,
                    }
                ]

        fake_repository = FakeRepository()

        with patch("app.api.routes_resume.get_resume_repository", return_value=fake_repository):
            response = TestClient(app).get("/api/resumes?userId=user-123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_repository.requested_user_id, "user-123")
        self.assertEqual(response.json()[0]["userId"], "user-123")


class ResumeImageEndpointTests(unittest.TestCase):
    def test_upload_resume_image_saves_file_and_returns_avatar_url(self) -> None:
        class FakeRepository:
            def __init__(self) -> None:
                self.saved_image_url: str | None = None
                self.saved_metadata: dict | None = None

            async def get(self, resume_id: str, user_id: str | None = None) -> dict:
                return {
                    "id": resume_id,
                    "resumeId": resume_id,
                    "userId": user_id,
                    "version": 1,
                    "status": "parsed",
                    "profile": {"data": {"name": "Alex Morgan", "sections": []}},
                    "metadata": {"filename": "alex.pdf"},
                    "avatar": "",
                    "withPhoto": False,
                }

            async def save_image(
                self,
                resume_id: str,
                image_url: str,
                image_metadata: dict,
                user_id: str | None = None,
            ) -> dict:
                self.saved_image_url = image_url
                self.saved_metadata = image_metadata
                return {
                    "id": resume_id,
                    "resumeId": resume_id,
                    "userId": user_id,
                    "version": 1,
                    "status": "parsed",
                    "profile": {"data": {"name": "Alex Morgan", "sections": []}},
                    "metadata": {"filename": "alex.pdf"},
                    "avatar": image_url,
                    "withPhoto": True,
                }

        image = BytesIO()
        Image.new("RGB", (1, 1), color="white").save(image, format="PNG")
        fake_repository = FakeRepository()

        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                MONGO_URI="mongodb://example",
                RESUME_IMAGE_STORAGE_DIR=temp_dir,
            )
            app.dependency_overrides[get_settings] = lambda: settings
            try:
                with patch("app.api.routes_resume.get_resume_repository", return_value=fake_repository):
                    response = TestClient(app).post(
                        "/api/resumes/resume123/image",
                        files={"file": ("avatar.png", image.getvalue(), "image/png")},
                    )
            finally:
                app.dependency_overrides.clear()

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["withPhoto"])
            self.assertTrue(payload["avatar"].startswith("http://testserver/api/resumes/images/resume123-"))
            self.assertIsNotNone(fake_repository.saved_metadata)
            saved_filename = fake_repository.saved_metadata["filename"]
            self.assertEqual(fake_repository.saved_metadata["objectKey"], saved_filename)
            self.assertEqual(fake_repository.saved_metadata["storageBackend"], "local")
            self.assertEqual(fake_repository.saved_metadata["contentType"], "image/png")
            self.assertTrue((LocalResumeImageStorage(temp_dir).storage_dir / saved_filename).is_file())

    def test_s3_storage_factory_uses_railway_credentials(self) -> None:
        settings = Settings(
            RESUME_IMAGE_STORAGE_BACKEND="s3",
            S3_ENDPOINT_URL="https://t3.storageapi.dev",
            S3_REGION="auto",
            S3_BUCKET_NAME="recorded-bottle-uayuz3vz5",
            S3_ACCESS_KEY_ID="access-key",
            S3_SECRET_ACCESS_KEY="secret-key",
        )

        with patch("app.api.routes_resume.S3ResumeImageStorage") as storage_class:
            storage = get_resume_image_storage(settings)

        self.assertEqual(storage, storage_class.return_value)
        storage_class.assert_called_once_with(
            endpoint_url="https://t3.storageapi.dev",
            region_name="auto",
            bucket_name="recorded-bottle-uayuz3vz5",
            access_key_id="access-key",
            secret_access_key="secret-key",
            key_prefix="resume-images",
        )


class LLMClientTests(unittest.IsolatedAsyncioTestCase):
    def test_get_llm_client_keeps_openai_provider_default(self) -> None:
        settings = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="openai-key")

        client = get_llm_client(settings)

        self.assertIsInstance(client, OpenAIClient)

    def test_get_llm_client_rejects_non_openai_provider(self) -> None:
        settings = Settings(LLM_PROVIDER="unsupported", OPENAI_API_KEY="openai-key")

        with self.assertRaises(RuntimeError) as error:
            get_llm_client(settings)

        self.assertIn("Only 'openai' is supported", str(error.exception))

    async def test_openai_client_extracts_json_from_chat_completion_response(self) -> None:
        settings = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="openai-key", OPENAI_MODEL="openai-test")
        response_payload = {"choices": [{"message": {"content": '{"profile":{"data":{"name":"Alex","sections":[]}}}'}}]}

        fake_response = unittest.mock.Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = response_payload
        fake_response.text = "ok"

        fake_http_client = unittest.mock.Mock()
        fake_http_client.__aenter__ = AsyncMock(return_value=fake_http_client)
        fake_http_client.__aexit__ = AsyncMock(return_value=None)
        fake_http_client.post = AsyncMock(return_value=fake_response)

        with patch("app.core.llm_client.httpx.AsyncClient", return_value=fake_http_client):
            profile = await OpenAIClient(settings).extract_resume_profile("Resume text", None)

        self.assertEqual(profile["profile"]["data"]["name"], "Alex")
        fake_http_client.post.assert_awaited_once()
        _, kwargs = fake_http_client.post.await_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer openai-key")
        self.assertEqual(kwargs["json"]["model"], "openai-test")
        self.assertEqual(kwargs["json"]["response_format"], {"type": "json_object"})

    async def test_openai_client_rephrases_text_with_resume_prompt(self) -> None:
        settings = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="openai-key", OPENAI_MODEL="openai-test")
        response_payload = {"choices": [{"message": {"content": '{"rephrasedText":"Built and maintained scalable REST APIs."}'}}]}

        fake_response = unittest.mock.Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = response_payload
        fake_response.text = "ok"

        fake_http_client = unittest.mock.Mock()
        fake_http_client.__aenter__ = AsyncMock(return_value=fake_http_client)
        fake_http_client.__aexit__ = AsyncMock(return_value=None)
        fake_http_client.post = AsyncMock(return_value=fake_response)

        with patch("app.core.llm_client.httpx.AsyncClient", return_value=fake_http_client):
            response = await OpenAIClient(settings).rephrase_resume_text("built APIs")

        self.assertEqual(response["rephrasedText"], "Built and maintained scalable REST APIs.")
        fake_http_client.post.assert_awaited_once()
        _, kwargs = fake_http_client.post.await_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer openai-key")
        self.assertEqual(kwargs["json"]["model"], "openai-test")
        self.assertEqual(kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["json"]["messages"][0]["content"].count("Rephrase ONLY"), 1)
        self.assertIn("Preserve the input structure", kwargs["json"]["messages"][0]["content"])
        self.assertIn("built APIs", kwargs["json"]["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
