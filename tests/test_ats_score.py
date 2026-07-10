import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.ats_score_service import calculate_ats_score, resume_json_to_text


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

class AtsEndpointTests(unittest.TestCase):
    def test_ats_score_endpoint_reads_parsed_resume(self) -> None:
        class FakeRepository:
            def __init__(self) -> None:
                self.requested_user_id: str | None = None

            async def get(
                self,
                resume_id: str,
                user_id: str | None = None,
            ) -> dict:
                self.requested_user_id = user_id
                return {"resumeId": resume_id, "profile": build_strong_resume()}

        fake_repository = FakeRepository()

        with patch("app.api.routes_ats.get_resume_repository", return_value=fake_repository):
            response = TestClient(app).get(
                "/api/resumes/resume123/ats-score",
                params={"userId": " user-123 "},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_repository.requested_user_id, "user-123")
        self.assertEqual(response.json()["resumeId"], "resume123")
        self.assertEqual(response.json()["source"], "parsed")
        self.assertNotIn("jobMatchAnalysis", response.json())

    def test_ats_score_endpoint_rejects_invalid_source_with_400(self) -> None:
        response = TestClient(app).get("/api/resumes/resume123/ats-score?source=raw")

        self.assertEqual(response.status_code, 400)

if __name__ == "__main__":
    unittest.main()
