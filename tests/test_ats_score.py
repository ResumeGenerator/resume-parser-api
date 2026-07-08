import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.ats_score_service import calculate_ats_score, compare_ats_scores, resume_json_to_text
from app.services.resume_repository import MongoResumeRepository


def build_strong_resume() -> dict:
    return {
        "candidateProfile": {
            "name": "Alex Morgan",
            "email": "alex@example.com",
            "phone": "+1 555 0100",
            "location": "Austin, TX",
            "linkedin": "https://linkedin.com/in/alexmorgan",
            "professionalHeadline": "Senior .NET Developer",
        },
        "professionalSummaryPoints": [
            "Senior .NET developer with 9 years of experience building Azure and Node.js platforms.",
            "Reduced API latency by 35% while leading CI/CD modernization.",
            "Designed REST APIs, microservices, and cloud integrations for high-volume products.",
        ],
        "coreSkills": ["C++", "C#", ".NET", "Node.js", "CI/CD", "Azure", "SQL", "Docker"],
        "skillsMatrix": {
            "backend": ["ASP.NET", "FastAPI", "REST", "Microservices"],
            "cloud": ["Azure", "Docker", "Kubernetes"],
        },
        "workExperience": [
            {
                "company": "Example SaaS",
                "role": "Senior Software Engineer",
                "start": "2020",
                "end": "Present",
                "responsibilities": ["Built APIs", "Led platform migrations"],
                "achievements": ["Reduced deployment time by 40%", "Improved reliability to 99.9%"],
                "tools": ["C#", ".NET", "Azure", "SQL", "CI/CD"],
            }
        ],
        "education": [
            {
                "degree": "Bachelor of Science",
                "fieldOfStudy": "Computer Science",
                "school": "Example University",
                "year": "2016",
            }
        ],
        "certificationsAndLicenses": [
            {
                "name": "Microsoft Azure Developer Associate",
                "issuer": "Microsoft",
                "year": "2024",
            }
        ],
    }


class AtsScoreServiceTests(unittest.TestCase):
    def test_resume_json_to_text_preserves_symbol_heavy_skills(self) -> None:
        text = resume_json_to_text({"skills": ["C++", "C#", ".NET", "Node.js", "CI/CD"]})

        self.assertIn("C++", text)
        self.assertIn("C#", text)
        self.assertIn(".NET", text)
        self.assertIn("Node.js", text)
        self.assertIn("CI/CD", text)

    def test_calculate_ats_score_includes_job_match_analysis(self) -> None:
        result = calculate_ats_score(build_strong_resume(), "Senior .NET Developer Azure CI/CD SQL")

        self.assertGreaterEqual(result["atsScore"], 80)
        self.assertEqual(result["scoreBreakdown"]["contactInfo"], 10)
        self.assertIsNotNone(result["jobMatchAnalysis"])
        self.assertIn(".net", result["jobMatchAnalysis"]["matchedKeywords"])
        self.assertIn("azure", result["jobMatchAnalysis"]["matchedKeywords"])

    def test_compare_ats_scores_reports_positive_improvement(self) -> None:
        parsed_resume = {
            "data": {
                "name": "Alex Morgan",
                "email": "alex@example.com",
                "sections": [
                    {"title": "Skills", "type": "skill", "items": [{"name": "C#", "aiGenerated": False}]}
                ],
            }
        }

        result = compare_ats_scores(parsed_resume, build_strong_resume())

        self.assertGreater(result["improvement"], 0)
        self.assertEqual(result["editedResume"]["scoreLevel"], "Excellent")


class AtsRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_resume_by_id_reads_edited_collection_for_edited_source(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.collection = unittest.mock.Mock()
        repository.edited_collection = unittest.mock.Mock()
        repository.edited_collection.find_one = AsyncMock(return_value={"resumeId": "resume123"})

        document = await repository.get_resume_by_id("resume123", "edited")

        self.assertEqual(document, {"resumeId": "resume123"})
        repository.edited_collection.find_one.assert_awaited_once_with(
            {"$or": [{"resumeId": "resume123"}, {"id": "resume123"}]},
            sort=[("updatedAt", -1)],
        )

    async def test_get_resume_by_id_edited_source_falls_back_to_main_collection_with_user_id(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.collection = unittest.mock.Mock()
        repository.edited_collection = unittest.mock.Mock()
        original_resume = {"resumeId": "resume123", "userId": "user-123"}
        repository.edited_collection.find_one = AsyncMock(return_value=None)
        repository.collection.find_one = AsyncMock(return_value=original_resume)

        document = await repository.get_resume_by_id("resume123", "edited", user_id=" user-123 ")

        expected_query = {
            "$and": [
                {"$or": [{"resumeId": "resume123"}, {"id": "resume123"}]},
                {"userId": "user-123"},
            ]
        }
        self.assertEqual(document, original_resume)
        repository.edited_collection.find_one.assert_awaited_once_with(
            expected_query,
            sort=[("updatedAt", -1)],
        )
        repository.collection.find_one.assert_awaited_once_with(expected_query)

    async def test_get_resume_by_id_edited_source_resolves_stable_id_from_main_collection(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.collection = unittest.mock.Mock()
        repository.edited_collection = unittest.mock.Mock()
        repository.collection.find_one = AsyncMock(return_value={"_id": "mongo-id", "resumeId": "stable-id"})
        repository.edited_collection.find_one = AsyncMock(side_effect=[None, {"resumeId": "stable-id"}])

        document = await repository.get_resume_by_id("mongo-id", "edited")

        self.assertEqual(document, {"resumeId": "stable-id"})
        self.assertEqual(repository.edited_collection.find_one.await_count, 2)
        repository.edited_collection.find_one.assert_any_await(
            {"$or": [{"resumeId": "mongo-id"}, {"id": "mongo-id"}]},
            sort=[("updatedAt", -1)],
        )
        repository.edited_collection.find_one.assert_any_await(
            {"$or": [{"resumeId": "stable-id"}, {"id": "stable-id"}]},
            sort=[("updatedAt", -1)],
        )

    async def test_get_parsed_and_edited_resume_uses_stable_resume_id(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.collection = unittest.mock.Mock()
        repository.edited_collection = unittest.mock.Mock()
        repository.collection.find_one = AsyncMock(return_value={"_id": "mongo-id", "resumeId": "stable-id"})
        repository.edited_collection.find_one = AsyncMock(return_value={"resumeId": "stable-id"})

        parsed_resume, edited_resume = await repository.get_parsed_and_edited_resume("mongo-id")

        self.assertEqual(parsed_resume["resumeId"], "stable-id")
        self.assertEqual(edited_resume["resumeId"], "stable-id")
        repository.edited_collection.find_one.assert_awaited_once_with(
            {"$or": [{"resumeId": "stable-id"}, {"id": "stable-id"}]},
            sort=[("updatedAt", -1)],
        )


class AtsEndpointTests(unittest.TestCase):
    def test_ats_score_endpoint_defaults_to_edited_source(self) -> None:
        class FakeRepository:
            def __init__(self) -> None:
                self.requested_source: str | None = None
                self.requested_user_id: str | None = None

            async def get_resume_by_id(
                self,
                resume_id: str,
                source: str,
                user_id: str | None = None,
            ) -> dict:
                self.requested_source = source
                self.requested_user_id = user_id
                return {"resumeId": resume_id, "profile": build_strong_resume()}

        fake_repository = FakeRepository()

        with patch("app.api.routes_ats.get_resume_repository", return_value=fake_repository):
            response = TestClient(app).get(
                "/api/resumes/resume123/ats-score",
                params={"userId": " user-123 "},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_repository.requested_source, "edited")
        self.assertEqual(fake_repository.requested_user_id, "user-123")
        self.assertEqual(response.json()["resumeId"], "resume123")
        self.assertEqual(response.json()["source"], "edited")
        self.assertNotIn("jobMatchAnalysis", response.json())

    def test_ats_score_endpoint_rejects_invalid_source_with_400(self) -> None:
        response = TestClient(app).get("/api/resumes/resume123/ats-score?source=raw")

        self.assertEqual(response.status_code, 400)

    def test_compare_ats_score_endpoint_returns_improvement(self) -> None:
        class FakeRepository:
            async def get_parsed_and_edited_resume(
                self,
                resume_id: str,
                user_id: str | None = None,
            ) -> tuple[dict, dict]:
                return (
                    {
                        "resumeId": resume_id,
                        "profile": {
                            "data": {
                                "name": "Alex Morgan",
                                "sections": [
                                    {
                                        "title": "Skills",
                                        "type": "skill",
                                        "items": [{"name": "C#", "aiGenerated": False}],
                                    }
                                ],
                            }
                        },
                    },
                    {"resumeId": resume_id, "profile": build_strong_resume()},
                )

        with patch("app.api.routes_ats.get_resume_repository", return_value=FakeRepository()):
            response = TestClient(app).get("/api/resumes/resume123/compare-ats-score")

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()["improvement"], 0)
        self.assertEqual(response.json()["resumeId"], "resume123")


if __name__ == "__main__":
    unittest.main()
