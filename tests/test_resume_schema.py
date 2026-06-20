import unittest

from app.models.resume_schema import ResumeProfile


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


if __name__ == "__main__":
    unittest.main()
