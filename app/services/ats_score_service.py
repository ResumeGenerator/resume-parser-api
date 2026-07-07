import re
from collections.abc import Iterable
from typing import Any


CONTACT_INFO_MAX = 10
SUMMARY_MAX = 10
SKILLS_MAX = 15
WORK_EXPERIENCE_MAX = 20
EDUCATION_MAX = 10
CERTIFICATIONS_MAX = 5
KEYWORDS_MAX = 20
FORMATTING_MAX = 10

SECTION_KEY_ALIASES = {
    "summary": {
        "summary",
        "professional summary",
        "professional summary points",
        "professional headline",
        "executive summary",
        "profile summary",
        "career summary",
    },
    "skills": {
        "skills",
        "skill",
        "core skills",
        "skills matrix",
        "technical skills",
        "technologies",
        "tools",
        "competencies",
    },
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "career history",
        "responsibilities",
        "achievements",
        "projects or case studies",
        "achievement bank",
    },
    "education": {
        "education",
        "educational background",
        "academic background",
        "qualifications",
    },
    "certifications": {
        "certifications",
        "certification",
        "certifications and licenses",
        "certificates",
        "licenses",
        "licences",
    },
}

EXPERIENCE_FIELD_ALIASES = {
    "company": {"company", "employer", "organization", "organisation", "client"},
    "role": {"role", "title", "position", "job title", "designation"},
    "responsibilities": {"responsibilities", "responsibility", "duties", "description", "overview"},
    "achievements": {"achievements", "achievement", "highlights", "accomplishments", "impact", "results"},
    "dates": {"start", "end", "from", "to", "dates", "duration", "period"},
    "tools": {"tools", "technologies", "technology", "tech stack", "environment", "platforms"},
}

EDUCATION_FIELD_ALIASES = {
    "degree": {"degree", "qualification", "program", "course"},
    "school": {"school", "university", "college", "institution"},
    "field": {"field", "field of study", "major", "specialization", "specialisation", "department"},
    "dates": {"year", "years", "start", "end", "graduation date"},
}

CERTIFICATION_FIELD_ALIASES = {
    "name": {"name", "certification", "certificate", "license", "licence", "title"},
    "issuer": {"issuer", "authority", "provider", "organization", "organisation"},
    "dates": {"date", "issued", "expires", "valid until", "year"},
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "using",
    "with",
    "within",
    "you",
    "your",
}

ACTION_VERBS = {
    "achieved",
    "architected",
    "built",
    "delivered",
    "designed",
    "developed",
    "drove",
    "implemented",
    "improved",
    "increased",
    "launched",
    "led",
    "managed",
    "migrated",
    "optimized",
    "owned",
    "reduced",
    "scaled",
    "streamlined",
}

TECHNICAL_KEYWORDS = {
    ".net",
    "agile",
    "angular",
    "api",
    "asp.net",
    "aws",
    "azure",
    "c#",
    "c++",
    "ci/cd",
    "docker",
    "fastapi",
    "gcp",
    "graphql",
    "java",
    "javascript",
    "kubernetes",
    "microservices",
    "mongodb",
    "node.js",
    "nosql",
    "postgresql",
    "python",
    "react",
    "rest",
    "sql",
    "typescript",
}

SPECIAL_KEYWORD_PATTERN = re.compile(
    r"(?<![\w+#./-])(?:ASP\.NET|Node\.js|CI/CD|C\+\+|C#|\.NET)(?![\w+#./-])",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(
    r"(?<![\w+#./-])(?:[A-Za-z0-9][A-Za-z0-9+#./-]*|\.[A-Za-z][A-Za-z0-9+#./-]*)(?![\w+#./-])"
)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{6,}\d)(?!\w)")
URL_PATTERN = re.compile(r"\b(?:https?://|www\.|linkedin\.com|github\.com)\S+", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
METRIC_PATTERN = re.compile(r"(?:\b\d+(?:\.\d+)?\s*(?:%|percent|x|k|m|million|billion)\b|\$\s*\d+)", re.IGNORECASE)
SPECIAL_CHARACTER_PATTERN = re.compile(r"[^A-Za-z0-9\s+#./,@:&()%'$-]")


def calculate_ats_score(resume_json: dict, job_description: str | None = None) -> dict:
    resume_text = resume_json_to_text(resume_json)
    job_description_text = (job_description or "").strip()

    strengths: list[str] = []
    weak_areas: list[str] = []
    missing_sections: list[str] = []
    formatting_risks: list[str] = []
    improvement_suggestions: list[str] = []

    contact_score, contact_notes = _score_contact_info(resume_json, resume_text)
    summary_score, summary_notes = _score_professional_summary(resume_json)
    skills_score, skills_notes = _score_skills(resume_json)
    experience_score, experience_notes = _score_work_experience(resume_json)
    education_score, education_notes = _score_education(resume_json)
    certifications_score, certification_notes = _score_certifications(resume_json)
    keyword_score, job_match_analysis, keyword_gaps = _score_keywords(resume_text, job_description_text)
    formatting_score, formatting_notes = _score_formatting(
        resume_json,
        resume_text,
        {
            "contactInfo": contact_score,
            "professionalSummary": summary_score,
            "skills": skills_score,
            "workExperience": experience_score,
            "education": education_score,
        },
    )

    _apply_notes(contact_notes, strengths, weak_areas, missing_sections, improvement_suggestions)
    _apply_notes(summary_notes, strengths, weak_areas, missing_sections, improvement_suggestions)
    _apply_notes(skills_notes, strengths, weak_areas, missing_sections, improvement_suggestions)
    _apply_notes(experience_notes, strengths, weak_areas, missing_sections, improvement_suggestions)
    _apply_notes(education_notes, strengths, weak_areas, missing_sections, improvement_suggestions)
    _apply_notes(certification_notes, strengths, weak_areas, missing_sections, improvement_suggestions)
    _apply_notes(formatting_notes, strengths, weak_areas, missing_sections, improvement_suggestions, formatting_risks)

    if keyword_score >= 15:
        strengths.append("Resume contains a healthy set of role-relevant keywords.")
    elif job_description_text:
        weak_areas.append("Keyword alignment with the job description needs improvement.")
        improvement_suggestions.append("Add the missing job description keywords where they truthfully match experience.")
    else:
        improvement_suggestions.append(
            "Provide a target job description to calculate a more precise keyword alignment score."
        )

    score_breakdown = {
        "contactInfo": contact_score,
        "professionalSummary": summary_score,
        "skills": skills_score,
        "workExperience": experience_score,
        "education": education_score,
        "certifications": certifications_score,
        "keywords": keyword_score,
        "formatting": formatting_score,
    }
    ats_score = max(0, min(100, sum(score_breakdown.values())))

    result = {
        "atsScore": ats_score,
        "scoreLevel": _score_level(ats_score),
        "summary": _score_summary(ats_score, bool(job_description_text)),
        "scoreBreakdown": score_breakdown,
        "strengths": _dedupe(strengths),
        "weakAreas": _dedupe(weak_areas),
        "missingSections": _dedupe(missing_sections),
        "keywordGaps": keyword_gaps,
        "formattingRisks": _dedupe(formatting_risks),
        "improvementSuggestions": _dedupe(improvement_suggestions),
    }
    if job_match_analysis is not None:
        result["jobMatchAnalysis"] = job_match_analysis

    return result


def compare_ats_scores(
    parsed_resume_json: dict,
    edited_resume_json: dict,
    job_description: str | None = None,
) -> dict:
    original_score = calculate_ats_score(parsed_resume_json, job_description)
    edited_score = calculate_ats_score(edited_resume_json, job_description)
    improvement = edited_score["atsScore"] - original_score["atsScore"]

    if improvement > 0:
        summary = f"Edited resume improved ATS readiness by {improvement} points."
    elif improvement < 0:
        summary = f"Edited resume reduced ATS readiness by {abs(improvement)} points."
    else:
        summary = "Edited resume has the same ATS readiness score as the original resume."

    return {
        "originalResume": {
            "atsScore": original_score["atsScore"],
            "scoreLevel": original_score["scoreLevel"],
        },
        "editedResume": {
            "atsScore": edited_score["atsScore"],
            "scoreLevel": edited_score["scoreLevel"],
        },
        "improvement": improvement,
        "summary": summary,
        "remainingSuggestions": edited_score["improvementSuggestions"],
    }


def resume_json_to_text(data: dict) -> str:
    parts: list[str] = []
    _collect_text_parts(data, parts)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _collect_text_parts(value: Any, parts: list[str]) -> None:
    if value is None:
        return

    if isinstance(value, dict):
        for key, nested_value in value.items():
            if _is_empty(nested_value):
                continue
            parts.append(_humanize_key(str(key)))
            _collect_text_parts(nested_value, parts)
        return

    if isinstance(value, list):
        for item in value:
            _collect_text_parts(item, parts)
        return

    if isinstance(value, str):
        text = value.strip()
        if text:
            parts.append(text)
        return

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parts.append(str(value))


def _score_contact_info(resume_json: dict, resume_text: str) -> tuple[int, dict[str, list[str]]]:
    contact_values = _collect_values_by_keys(
        resume_json,
        {
            "candidate profile",
            "contact",
            "contact info",
            "contact information",
            "data",
            "email",
            "phone",
            "location",
            "address",
            "linkedin",
            "links",
            "name",
            "full name",
            "candidate name",
        },
    )
    contact_text = " ".join([resume_text, *[resume_json_to_text(value) for value in contact_values if isinstance(value, dict)]])
    text_lower = contact_text.lower()

    has_email = bool(EMAIL_PATTERN.search(contact_text)) or _has_key_with_text(resume_json, {"email"})
    has_phone = bool(PHONE_PATTERN.search(contact_text)) or _has_key_with_text(resume_json, {"phone", "mobile"})
    has_name = _has_key_with_text(resume_json, {"name", "full name", "candidate name"})
    has_location = _has_key_with_text(resume_json, {"location", "address", "city", "country"})
    has_link = bool(URL_PATTERN.search(contact_text)) or any(
        value in text_lower for value in ("linkedin", "github", "portfolio")
    )

    score = 0
    score += 3 if has_email else 0
    score += 3 if has_phone else 0
    score += 2 if has_name else 0
    score += 1 if has_location else 0
    score += 1 if has_link else 0

    notes = _empty_notes()
    if score >= 8:
        notes["strengths"].append("Contact information is complete enough for recruiter follow-up.")
    else:
        notes["weakAreas"].append("Contact information is incomplete.")
        notes["missingSections"].append("Contact information")
        if not has_email:
            notes["suggestions"].append("Add a professional email address.")
        if not has_phone:
            notes["suggestions"].append("Add a reachable phone number.")
        if not has_name:
            notes["suggestions"].append("Add the candidate name in the resume header.")

    return min(CONTACT_INFO_MAX, score), notes


def _score_professional_summary(resume_json: dict) -> tuple[int, dict[str, list[str]]]:
    summary_values = _collect_section_values(resume_json, SECTION_KEY_ALIASES["summary"])
    summary_text = " ".join(_text_from_values(summary_values))
    headline_values = _collect_values_by_keys(resume_json, {"professional headline", "headline"})
    headline_text = " ".join(_text_from_values(headline_values))
    word_count = _word_count(summary_text)
    sentence_count = len(re.findall(r"[.!?]|(?:\n\s*[-*])", summary_text))

    score = 0
    if headline_text.strip():
        score += 2
    if summary_text.strip():
        score += 4
    if word_count >= 35:
        score += 2
    elif word_count >= 12:
        score += 1
    if sentence_count >= 2 or _list_like_count(summary_values) >= 3:
        score += 1
    if METRIC_PATTERN.search(summary_text):
        score += 1

    notes = _empty_notes()
    if score >= 8:
        notes["strengths"].append("Professional summary gives a clear snapshot of the candidate.")
    elif score > 0:
        notes["weakAreas"].append("Professional summary is present but could be stronger.")
        notes["suggestions"].append("Expand the professional summary with role focus, strengths, and measurable impact.")
    else:
        notes["weakAreas"].append("Professional summary is missing.")
        notes["missingSections"].append("Professional summary")
        notes["suggestions"].append("Add a concise professional summary tailored to the target role.")

    return min(SUMMARY_MAX, score), notes


def _score_skills(resume_json: dict) -> tuple[int, dict[str, list[str]]]:
    skills_values = _collect_section_values(resume_json, SECTION_KEY_ALIASES["skills"])
    skills_text = " ".join(_text_from_values(skills_values))
    skills = _extract_keywords(skills_text)
    has_core_skills = bool(_collect_values_by_keys(resume_json, {"core skills"}))
    has_skills_matrix = bool(_collect_values_by_keys(resume_json, {"skills matrix"}))
    technical_hits = {keyword for keyword in skills if keyword in TECHNICAL_KEYWORDS}

    score = 0
    if skills_text.strip():
        score += 5
    if len(skills) >= 15:
        score += 6
    elif len(skills) >= 8:
        score += 4
    elif len(skills) >= 4:
        score += 2
    if has_core_skills:
        score += 2
    if has_skills_matrix:
        score += 1
    if len(technical_hits) >= 3:
        score += 1

    notes = _empty_notes()
    if score >= 12:
        notes["strengths"].append("Skills section is well populated and easy to scan.")
    elif score > 0:
        notes["weakAreas"].append("Skills section needs more depth or clearer grouping.")
        notes["suggestions"].append("Group core skills and tools into concise categories.")
    else:
        notes["weakAreas"].append("Skills section is missing.")
        notes["missingSections"].append("Skills")
        notes["suggestions"].append("Add a dedicated skills section with relevant tools, platforms, and methods.")

    return min(SKILLS_MAX, score), notes


def _score_work_experience(resume_json: dict) -> tuple[int, dict[str, list[str]]]:
    experience_values = _collect_section_values(resume_json, SECTION_KEY_ALIASES["experience"])
    experience_items = _flatten_dict_items(experience_values)
    experience_text = " ".join(_text_from_values(experience_values))

    if not experience_text.strip():
        notes = _empty_notes()
        notes["weakAreas"].append("Work experience is missing.")
        notes["missingSections"].append("Work experience")
        notes["suggestions"].append("Add work experience with role, company, dates, responsibilities, and achievements.")
        return 0, notes

    field_presence = {
        field_name: any(_dict_has_matching_key(item, aliases) for item in experience_items)
        for field_name, aliases in EXPERIENCE_FIELD_ALIASES.items()
    }
    has_dates = field_presence["dates"] or bool(YEAR_PATTERN.search(experience_text))
    has_achievements = field_presence["achievements"] or bool(METRIC_PATTERN.search(experience_text))
    has_metrics = bool(METRIC_PATTERN.search(experience_text))

    score = 4
    if len(experience_items) >= 2:
        score += 2
    if field_presence["company"]:
        score += 2
    if field_presence["role"]:
        score += 2
    if has_dates:
        score += 3
    if field_presence["responsibilities"] or _word_count(experience_text) >= 60:
        score += 3
    if has_achievements:
        score += 3
    if has_metrics:
        score += 1
    if field_presence["tools"] or any(keyword in _extract_keywords(experience_text) for keyword in TECHNICAL_KEYWORDS):
        score += 2

    notes = _empty_notes()
    if score >= 16:
        notes["strengths"].append("Work experience includes strong structure and achievement detail.")
    else:
        notes["weakAreas"].append("Work experience could better show scope, tools, dates, or measurable achievements.")
        if not field_presence["company"] or not field_presence["role"]:
            notes["suggestions"].append("Include company and role for each work experience entry.")
        if not has_dates:
            notes["suggestions"].append("Add start and end dates for work experience entries.")
        if not has_metrics:
            notes["suggestions"].append("Add measurable achievements such as percentages, revenue, volume, or time saved.")

    return min(WORK_EXPERIENCE_MAX, score), notes


def _score_education(resume_json: dict) -> tuple[int, dict[str, list[str]]]:
    education_values = _collect_section_values(resume_json, SECTION_KEY_ALIASES["education"])
    education_items = _flatten_dict_items(education_values)
    education_text = " ".join(_text_from_values(education_values))

    if not education_text.strip():
        notes = _empty_notes()
        notes["weakAreas"].append("Education section is missing.")
        notes["missingSections"].append("Education")
        notes["suggestions"].append("Add education details with degree and institution.")
        return 0, notes

    has_degree = any(_dict_has_matching_key(item, EDUCATION_FIELD_ALIASES["degree"]) for item in education_items)
    has_school = any(_dict_has_matching_key(item, EDUCATION_FIELD_ALIASES["school"]) for item in education_items)
    has_field = any(_dict_has_matching_key(item, EDUCATION_FIELD_ALIASES["field"]) for item in education_items)
    has_dates = any(_dict_has_matching_key(item, EDUCATION_FIELD_ALIASES["dates"]) for item in education_items) or bool(
        YEAR_PATTERN.search(education_text)
    )

    score = 5
    score += 2 if has_degree else 0
    score += 2 if has_school else 0
    score += 1 if has_field or has_dates else 0

    notes = _empty_notes()
    if score >= 8:
        notes["strengths"].append("Education section is clear.")
    else:
        notes["weakAreas"].append("Education section needs more complete details.")
        notes["suggestions"].append("Include degree, institution, field of study, and graduation year where applicable.")

    return min(EDUCATION_MAX, score), notes


def _score_certifications(resume_json: dict) -> tuple[int, dict[str, list[str]]]:
    certification_values = _collect_section_values(resume_json, SECTION_KEY_ALIASES["certifications"])
    certification_items = _flatten_dict_items(certification_values)
    certification_text = " ".join(_text_from_values(certification_values))

    if not certification_text.strip():
        notes = _empty_notes()
        notes["weakAreas"].append("Certifications are not listed.")
        notes["missingSections"].append("Certifications")
        notes["suggestions"].append("Add relevant certifications or licenses if the target role values them.")
        return 0, notes

    has_name = any(_dict_has_matching_key(item, CERTIFICATION_FIELD_ALIASES["name"]) for item in certification_items)
    has_issuer = any(_dict_has_matching_key(item, CERTIFICATION_FIELD_ALIASES["issuer"]) for item in certification_items)
    has_dates = any(_dict_has_matching_key(item, CERTIFICATION_FIELD_ALIASES["dates"]) for item in certification_items) or bool(
        YEAR_PATTERN.search(certification_text)
    )

    score = 3
    score += 1 if has_name or certification_text else 0
    score += 1 if has_issuer or has_dates else 0
    notes = _empty_notes()
    if score >= 4:
        notes["strengths"].append("Relevant certifications or licenses are included.")
    else:
        notes["weakAreas"].append("Certification details are incomplete.")
        notes["suggestions"].append("Include certification issuer and year where available.")

    return min(CERTIFICATIONS_MAX, score), notes


def _score_keywords(resume_text: str, job_description: str) -> tuple[int, dict[str, Any] | None, list[str]]:
    resume_keywords = _extract_keywords(resume_text)
    if job_description:
        job_keywords = _extract_keywords(job_description)
        if not job_keywords:
            return 10, None, []

        matched = sorted(keyword for keyword in job_keywords if keyword in resume_keywords)
        missing = sorted(keyword for keyword in job_keywords if keyword not in resume_keywords)
        match_score = round(len(matched) / len(job_keywords) * 100)
        keyword_score = round(match_score / 100 * KEYWORDS_MAX)
        suggestions = []
        if missing:
            suggestions.append("Add missing job description keywords only where they accurately reflect experience.")

        return (
            min(KEYWORDS_MAX, keyword_score),
            {
                "matchScore": match_score,
                "matchLevel": _score_level(match_score),
                "matchedKeywords": matched[:20],
                "missingKeywords": missing[:20],
                "suggestions": suggestions,
            },
            missing[:20],
        )

    richness_score = 7
    if len(resume_keywords) >= 80:
        richness_score = 16
    elif len(resume_keywords) >= 50:
        richness_score = 14
    elif len(resume_keywords) >= 30:
        richness_score = 12
    elif len(resume_keywords) >= 15:
        richness_score = 10

    if resume_keywords.intersection(TECHNICAL_KEYWORDS):
        richness_score += 1
    if resume_keywords.intersection(ACTION_VERBS):
        richness_score += 1

    return min(16, richness_score), None, []


def _score_formatting(
    resume_json: dict,
    resume_text: str,
    section_scores: dict[str, int],
) -> tuple[int, dict[str, list[str]]]:
    score = FORMATTING_MAX
    risks: list[str] = []

    if _word_count(resume_text) < 120:
        score -= 2
        risks.append("Resume content is very short for ATS analysis.")
    if len(resume_text) < 400:
        score -= 1
    if _special_character_ratio(resume_text) > 0.08:
        score -= 2
        risks.append("Resume text contains a high ratio of unusual special characters.")
    if re.search(r"\S{80,}", resume_text):
        score -= 1
        risks.append("Resume contains very long unbroken text that may not parse cleanly.")

    critical_missing = [
        label
        for label, key in (
            ("contact information", "contactInfo"),
            ("professional summary", "professionalSummary"),
            ("skills", "skills"),
            ("work experience", "workExperience"),
            ("education", "education"),
        )
        if section_scores.get(key, 0) == 0
    ]
    if critical_missing:
        score -= min(4, len(critical_missing))
        risks.append("Missing critical resume sections: " + ", ".join(critical_missing) + ".")

    if not isinstance(resume_json, dict) or not resume_json:
        score = 0
        risks.append("Resume JSON is empty or invalid.")

    notes = _empty_notes()
    if risks:
        notes["weakAreas"].append("ATS readability has formatting or structure risks.")
        notes["formattingRisks"].extend(risks)
        notes["suggestions"].append("Keep the resume structure simple, complete, and section-based.")
    else:
        notes["strengths"].append("Structured JSON format is generally ATS-readable.")

    return max(0, min(FORMATTING_MAX, score)), notes


def _collect_values_by_keys(data: Any, aliases: set[str]) -> list[Any]:
    matches: list[Any] = []
    normalized_aliases = {_normalize_label(alias) for alias in aliases}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested_value in value.items():
                if _normalize_label(str(key)) in normalized_aliases:
                    matches.append(nested_value)
                visit(nested_value)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data)
    return matches


def _collect_section_values(data: Any, aliases: set[str]) -> list[Any]:
    matches = _collect_values_by_keys(data, aliases)
    normalized_aliases = {_normalize_label(alias) for alias in aliases}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            label_values = [
                str(value.get(field, ""))
                for field in ("type", "title", "section", "sectionType", "name", "label", "blockType")
            ]
            label_text = _normalize_label(" ".join(label_values))
            if label_text and any(alias in label_text or label_text in alias for alias in normalized_aliases):
                for content_key in ("items", "content", "text", "bullets", "points", "entries", "blocks"):
                    if content_key in value and not _is_empty(value[content_key]):
                        matches.append(value[content_key])
                        break
                else:
                    matches.append(value)

            for nested_value in value.values():
                visit(nested_value)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data)
    return matches


def _flatten_dict_items(values: Iterable[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            items.append(value)
            for nested_value in value.values():
                visit(nested_value)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for value in values:
        visit(value)
    return items


def _dict_has_matching_key(item: dict[str, Any], aliases: set[str]) -> bool:
    normalized_aliases = {_normalize_label(alias) for alias in aliases}
    for key, value in item.items():
        if _normalize_label(str(key)) in normalized_aliases and not _is_empty(value):
            return True
    return False


def _has_key_with_text(data: Any, aliases: set[str]) -> bool:
    return any(not _is_empty(value) for value in _collect_values_by_keys(data, aliases))


def _text_from_values(values: Iterable[Any]) -> list[str]:
    text_values: list[str] = []
    for value in values:
        if isinstance(value, dict):
            text_values.append(resume_json_to_text(value))
        elif isinstance(value, list):
            text_values.extend(_text_from_values(value))
        elif isinstance(value, str):
            if value.strip():
                text_values.append(value.strip())
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            text_values.append(str(value))
    return text_values


def _extract_keywords(text: str) -> set[str]:
    keywords: set[str] = set()
    for match in SPECIAL_KEYWORD_PATTERN.finditer(text):
        keywords.add(_normalize_keyword(match.group(0)))

    for match in TOKEN_PATTERN.finditer(text):
        token = _normalize_keyword(match.group(0))
        if not token or token in STOPWORDS:
            continue
        if token.isdigit():
            continue
        if len(token) < 2 and token not in {"c"}:
            continue
        keywords.add(token)

    return keywords


def _normalize_keyword(value: str) -> str:
    token = value.strip().strip(",;:()[]{}").lower()
    token = re.sub(r"\s+", " ", token)
    return token


def _normalize_label(value: str) -> str:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    spaced = re.sub(r"[_\-/]+", " ", spaced)
    spaced = re.sub(r"[^A-Za-z0-9+#.]+", " ", spaced)
    return re.sub(r"\s+", " ", spaced).strip().lower()


def _humanize_key(value: str) -> str:
    return _normalize_label(value)


def _word_count(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))


def _list_like_count(values: Iterable[Any]) -> int:
    count = 0
    for value in values:
        if isinstance(value, list):
            count += len([item for item in value if not _is_empty(item)])
        elif isinstance(value, str):
            count += len([line for line in value.splitlines() if line.strip()])
    return count


def _special_character_ratio(text: str) -> float:
    if not text:
        return 0.0
    return len(SPECIAL_CHARACTER_PATTERN.findall(text)) / len(text)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _score_level(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 55:
        return "Moderate"
    if score >= 40:
        return "Weak"
    return "Poor"


def _score_summary(score: int, has_job_description: bool) -> str:
    if score >= 85:
        return "Resume is highly ATS-ready with strong structure, content depth, and keyword coverage."
    if score >= 70:
        if has_job_description:
            return "Resume is ATS-friendly but can be improved with stronger measurable achievements and keyword alignment."
        return "Resume is ATS-friendly but can be improved with a target job description and stronger measurable achievements."
    if score >= 55:
        return "Resume has a usable foundation but needs stronger sections, clearer achievements, and better keyword coverage."
    if score >= 40:
        return "Resume has notable ATS readiness gaps across critical sections and content depth."
    return "Resume is not yet ATS-ready and needs substantial improvements before submission."


def _empty_notes() -> dict[str, list[str]]:
    return {
        "strengths": [],
        "weakAreas": [],
        "missingSections": [],
        "suggestions": [],
        "formattingRisks": [],
    }


def _apply_notes(
    notes: dict[str, list[str]],
    strengths: list[str],
    weak_areas: list[str],
    missing_sections: list[str],
    suggestions: list[str],
    formatting_risks: list[str] | None = None,
) -> None:
    strengths.extend(notes.get("strengths", []))
    weak_areas.extend(notes.get("weakAreas", []))
    missing_sections.extend(notes.get("missingSections", []))
    suggestions.extend(notes.get("suggestions", []))
    if formatting_risks is not None:
        formatting_risks.extend(notes.get("formattingRisks", []))


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
