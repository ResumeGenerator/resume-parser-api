import unittest
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.core.config import Settings
from app.core.llm_client import OpenAIClient, get_llm_client
from app.models.resume_schema import ResumeProfile, ResumeRephraseRequest
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
