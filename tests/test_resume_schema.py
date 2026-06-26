import unittest

from pydantic import ValidationError

from app.models.resume_schema import ResumeProfile, ResumeTemplateSaveRequest
from app.services.resume_parser import normalize_resume_profile_payload


class ResumeSchemaTests(unittest.TestCase):
    def test_total_experience_years_accepts_llm_numeric_strings(self) -> None:
        cases = {
            "8+": 8.0,
            "10 years": 10.0,
            "15+ years": 15.0,
            "10.5 years": 10.5,
            "1,200+ hours": 1200.0,
        }

        for value, expected in cases.items():
            with self.subTest(value=value):
                profile = ResumeProfile.model_validate(
                    {"candidateProfile": {"totalExperienceYears": value}}
                )
                self.assertEqual(profile.candidateProfile.totalExperienceYears, expected)

    def test_total_experience_years_uses_none_for_missing_or_non_numeric_values(self) -> None:
        for value in ("", None, "not specified", True):
            with self.subTest(value=value):
                profile = ResumeProfile.model_validate(
                    {"candidateProfile": {"totalExperienceYears": value}}
                )
                self.assertIsNone(profile.candidateProfile.totalExperienceYears)

    def test_service_payload_normalizer_converts_total_experience_years(self) -> None:
        payload = {"candidateProfile": {"totalExperienceYears": "8+"}}

        normalized = normalize_resume_profile_payload(payload)

        self.assertEqual(normalized["candidateProfile"]["totalExperienceYears"], 8.0)

    def test_template_resume_payload_accepts_renderer_shape(self) -> None:
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

        request = ResumeTemplateSaveRequest.model_validate(payload)

        self.assertEqual(request.template, "sydney")
        self.assertEqual(request.data.email, "bijum777@gmail.com")
        self.assertEqual(request.data.sections[0].items, payload["data"]["sections"][0]["items"])
        self.assertEqual(request.data.sections[1].items[0]["company"], "Lexis Nexis")

    def test_template_resume_payload_forbids_unexpected_top_level_fields(self) -> None:
        payload = {
            "template": "sydney",
            "format": "html",
            "data": {"sections": []},
            "unexpected": True,
        }

        with self.assertRaises(ValidationError):
            ResumeTemplateSaveRequest.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
