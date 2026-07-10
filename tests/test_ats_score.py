import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.ats_score_service import calculate_ats_score, resume_json_to_text
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


class AtsRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_ats_calculation_updates_parsed_resume(self) -> None:
        repository = MongoResumeRepository.__new__(MongoResumeRepository)
        repository.database_name = "resume_parser"
        repository.collection_name = "parsed_resumes"
        repository.collection = unittest.mock.Mock()
        repository.collection.find_one = AsyncMock(
            return_value={
                "_id": "parsed-mongo-id",
                "resumeId": "resume123",
                "userId": "user-123",
            }
        )
        repository.collection.update_one = AsyncMock(
            return_value=unittest.mock.Mock(matched_count=1)
        )
        calculation = calculate_ats_score(build_strong_resume())

        stored = await repository.save_ats_calculation(
            "resume123",
            calculation,
            user_id=" user-123 ",
        )

        self.assertTrue(stored)
        update_filter, update_document = repository.collection.update_one.await_args.args
        self.assertEqual(update_filter, {"_id": "parsed-mongo-id"})
        self.assertEqual(update_document["$set"]["atsScore"], calculation["atsScore"])
        self.assertEqual(update_document["$set"]["atsCalculation"], calculation)
        self.assertIn("atsCalculatedAt", update_document["$set"])
        self.assertNotIn("editedResume", update_document["$set"])


class AtsEndpointTests(unittest.TestCase):
    def test_ats_score_endpoint_reads_parsed_resume(self) -> None:
        class FakeRepository:
            def __init__(self) -> None:
                self.requested_user_id: str | None = None
                self.stored_user_id: str | None = None

            async def get(
                self,
                resume_id: str,
                user_id: str | None = None,
            ) -> dict:
                self.requested_user_id = user_id
                return {"resumeId": resume_id, "profile": build_strong_resume()}

            async def save_ats_calculation(
                self,
                resume_id: str,
                calculation: dict,
                user_id: str | None = None,
            ) -> bool:
                self.stored_user_id = user_id
                return True

        fake_repository = FakeRepository()

        with patch("app.api.routes_ats.get_resume_repository", return_value=fake_repository):
            response = TestClient(app).get(
                "/api/resumes/resume123/ats-score",
                params={"userId": " user-123 "},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_repository.requested_user_id, "user-123")
        self.assertEqual(fake_repository.stored_user_id, "user-123")
        self.assertEqual(response.json()["resumeId"], "resume123")
        self.assertEqual(response.json()["source"], "parsed")
        self.assertNotIn("jobMatchAnalysis", response.json())

    def test_ats_score_endpoint_rejects_invalid_source_with_400(self) -> None:
        for source in ("edited", "raw"):
            with self.subTest(source=source):
                response = TestClient(app).get(
                    "/api/resumes/resume123/ats-score",
                    params={"source": source},
                )

                self.assertEqual(response.status_code, 400)

if __name__ == "__main__":
    unittest.main()
