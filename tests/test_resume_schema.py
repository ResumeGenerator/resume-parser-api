import unittest
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from pydantic import ValidationError

from app.core.config import Settings
from app.core.llm_client import GeminiClient, OpenAIClient, get_llm_client
from app.models.resume_schema import ResumeProfile
from app.services.resume_parser import normalize_resume_profile_payload
from app.services.resume_repository import MongoResumeRepository


class ResumeSchemaTests(unittest.TestCase):
    def test_service_payload_normalizer_unwraps_profile_payload(self) -> None:
        payload = {
            "profile": {
                "data": {"name": "Biju Manayagaths", "sections": []},
            }
        }

        normalized = normalize_resume_profile_payload(payload)

        self.assertEqual(normalized["data"]["name"], "Biju Manayagaths")

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
                            {"name": "Development", "level": "Beginner"},
                            {"name": "Cloud computing", "level": "Intermediate"},
                        ],
                    },
                ],
            },
        }

        profile = ResumeProfile.model_validate(payload)

        self.assertEqual(profile.data.email, "bijum777@gmail.com")
        self.assertEqual(profile.data.sections[0].items, payload["data"]["sections"][0]["items"])
        self.assertEqual(profile.data.sections[1].items[0].company, "Lexis Nexis")

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


class MongoResumeRepositoryTests(unittest.IsolatedAsyncioTestCase):
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
        )

        self.assertTrue(ObjectId.is_valid(resume_id))
        repository.collection.insert_one.assert_awaited_once()
        saved_document = repository.collection.insert_one.await_args.args[0]
        self.assertEqual(resume_id, str(saved_document["_id"]))
        self.assertEqual(saved_document["resumeId"], str(saved_document["_id"]))
        self.assertEqual(saved_document["version"], 1)
        self.assertEqual(saved_document["status"], "parsed")
        self.assertEqual(saved_document["profile"]["data"]["name"], "Alex Morgan")
        self.assertEqual(saved_document["source"]["createdFrom"], "parse")


class LLMClientTests(unittest.IsolatedAsyncioTestCase):
    def test_get_llm_client_supports_configured_gemini_provider(self) -> None:
        settings = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="gemini-key")

        client = get_llm_client(settings)

        self.assertIsInstance(client, GeminiClient)

    def test_get_llm_client_keeps_openai_provider_default(self) -> None:
        settings = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="openai-key")

        client = get_llm_client(settings)

        self.assertIsInstance(client, OpenAIClient)

    async def test_gemini_client_extracts_json_from_generate_content_response(self) -> None:
        settings = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="gemini-key", GEMINI_MODEL="gemini-test")
        response_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"profile":{"data":{"name":"Alex","sections":[]}}}'
                            }
                        ]
                    }
                }
            ]
        }

        fake_response = unittest.mock.Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = response_payload
        fake_response.text = "ok"

        fake_http_client = unittest.mock.Mock()
        fake_http_client.__aenter__ = AsyncMock(return_value=fake_http_client)
        fake_http_client.__aexit__ = AsyncMock(return_value=None)
        fake_http_client.post = AsyncMock(return_value=fake_response)

        with patch("app.core.llm_client.httpx.AsyncClient", return_value=fake_http_client):
            profile = await GeminiClient(settings).extract_resume_profile("Resume text", None)

        self.assertEqual(profile["profile"]["data"]["name"], "Alex")
        fake_http_client.post.assert_awaited_once()
        _, kwargs = fake_http_client.post.await_args
        self.assertEqual(kwargs["params"], {"key": "gemini-key"})
        self.assertEqual(kwargs["json"]["generationConfig"]["responseMimeType"], "application/json")


if __name__ == "__main__":
    unittest.main()
