import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from pydantic import ValidationError

from app.core.config import Settings
from app.core.llm_client import GeminiClient, OpenAIClient, get_llm_client
from app.models.resume_schema import ResumeProfile, ResumeTemplateSaveRequest
from app.services.resume_parser import normalize_resume_profile_payload
from app.services.resume_preview import build_resume_preview_html
from app.services.resume_repository import serialize_resume_document, serialize_resume_list_item


class ResumeSchemaTests(unittest.TestCase):
    def test_service_payload_normalizer_unwraps_profile_payload(self) -> None:
        payload = {
            "profile": {
                "template": "strassburg",
                "format": "html",
                "data": {"name": "Biju Manayagaths", "sections": []},
            }
        }

        normalized = normalize_resume_profile_payload(payload)

        self.assertEqual(normalized["data"]["name"], "Biju Manayagaths")

    def test_resume_profile_accepts_renderer_shape(self) -> None:
        payload = {
            "template": "sydney",
            "format": "html",
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
            "font": "Arial",
            "color": "#000000",
            "withPhoto": True,
            "avatar": "https://example.com/avatar.png?v=1782462038256",
            "contactsTitle": "Contacts",
            "detailsTitle": "Details",
        }

        profile = ResumeProfile.model_validate(payload)

        self.assertEqual(profile.template, "sydney")
        self.assertEqual(profile.data.email, "bijum777@gmail.com")
        self.assertEqual(profile.data.sections[0].items, payload["data"]["sections"][0]["items"])
        self.assertEqual(profile.data.sections[1].items[0].company, "Lexis Nexis")

    def test_template_resume_payload_accepts_renderer_shape_with_metadata(self) -> None:
        payload = {
            "template": "sydney",
            "format": "html",
            "data": {"name": "Biju Manayagaths", "sections": []},
            "metadata": {"source": "ui"},
            "source": {"editedBy": "user"},
        }

        request = ResumeTemplateSaveRequest.model_validate(payload)

        self.assertEqual(request.template, "sydney")
        self.assertEqual(request.data.name, "Biju Manayagaths")
        self.assertEqual(request.metadata["source"], "ui")

    def test_template_resume_payload_forbids_unexpected_top_level_fields(self) -> None:
        payload = {
            "template": "sydney",
            "format": "html",
            "data": {"sections": []},
            "unexpected": True,
        }

        with self.assertRaises(ValidationError):
            ResumeTemplateSaveRequest.model_validate(payload)

    def test_preview_html_escapes_resume_content(self) -> None:
        profile = ResumeProfile.model_validate(
            {
                "data": {
                    "name": "<Alex>",
                    "title": "Engineer",
                    "email": "alex@example.com",
                    "sections": [
                        {
                            "title": "Professional summary",
                            "type": "summary",
                            "items": "<script>alert(1)</script>",
                        }
                    ],
                },
                "font": "Arial; color:red",
                "color": "red;background:url(javascript:alert(1))",
            }
        )

        html = build_resume_preview_html(profile)

        self.assertIn("&lt;Alex&gt;", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("color: #000000;", html)

    def test_versioned_resume_serialization_uses_stable_resume_id(self) -> None:
        resume_id = str(ObjectId())
        version_document_id = ObjectId()
        document = {
            "_id": version_document_id,
            "resumeId": resume_id,
            "version": 2,
            "status": "edited",
            "profile": {"data": {"name": "Alex", "email": "alex@example.com", "title": "Engineer"}},
            "metadata": {"filename": "alex.pdf"},
            "source": {},
            "createdAt": datetime(2026, 1, 1, tzinfo=UTC),
            "updatedAt": datetime(2026, 1, 2, tzinfo=UTC),
        }

        serialized_document = serialize_resume_document(document)
        list_item = serialize_resume_list_item(document)

        self.assertEqual(serialized_document["id"], resume_id)
        self.assertEqual(serialized_document["resumeId"], resume_id)
        self.assertEqual(serialized_document["version"], 2)
        self.assertEqual(list_item["id"], resume_id)
        self.assertEqual(list_item["candidateName"], "Alex")


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
                                "text": '{"profile":{"template":"strassburg","format":"html","data":{"name":"Alex","sections":[]}}}'
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
