import re

from fastapi import HTTPException, status


SECTION_PATTERNS = [
    r"\b(professional\s+summary|summary|profile|objective)\b",
    r"\b(work\s+experience|professional\s+experience|employment\s+history|experience)\b",
    r"\b(education|academic\s+background)\b",
    r"\b(skills|technical\s+skills|core\s+competencies|competencies)\b",
    r"\b(projects|project\s+experience)\b",
    r"\b(certifications?|licenses?)\b",
    r"\b(achievements?|accomplishments?|awards)\b",
]

CONTACT_PATTERNS = [
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    r"(\+?\d[\d\s().-]{7,}\d)",
    r"\b(linkedin\.com|github\.com|portfolio|www\.)\b",
]

CAREER_TERMS = [
    "analyst",
    "architect",
    "assistant",
    "associate",
    "consultant",
    "coordinator",
    "developer",
    "director",
    "engineer",
    "executive",
    "lead",
    "manager",
    "officer",
    "specialist",
    "supervisor",
    "technician",
]

JOB_POSTING_PATTERNS = [
    r"\bapply\s+now\b",
    r"\bwe\s+are\s+(looking|seeking|hiring)\b",
    r"\bjob\s+description\b",
    r"\babout\s+(us|the\s+company)\b",
    r"\bequal\s+opportunity\s+employer\b",
    r"\bqualified\s+candidates\b",
]

RECEIPT_OR_INVOICE_PATTERNS = [
    r"\breceipt\b",
    r"\binvoice\s+number\b",
    r"\breceipt\s+number\b",
    r"\bdate\s+paid\b",
    r"\bbill\s+to\b",
    r"\bamount\b",
    r"\bunit\s+price\b",
    r"\bqty\b",
    r"\bpaid\s+on\b",
    r"\bpayment\b",
    r"\bbilling\b",
]


def raise_non_resume_error(reason: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "message": "Uploaded document does not appear to be a resume.",
            "reason": reason,
        },
    )


def validate_resume_document(text: str) -> None:
    normalized = text.lower()
    word_count = len(re.findall(r"\b\w+\b", normalized))
    section_count = sum(1 for pattern in SECTION_PATTERNS if re.search(pattern, normalized))
    contact_count = sum(1 for pattern in CONTACT_PATTERNS if re.search(pattern, text, re.IGNORECASE))
    date_count = len(
        re.findall(
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)?[a-z]*\.?\s*\d{4}\b|\b\d{4}\s*-\s*(?:present|current|\d{4})\b",
            normalized,
        )
    )
    career_term_count = sum(normalized.count(term) for term in CAREER_TERMS)
    bullet_count = len(re.findall(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", text))
    job_posting_count = sum(1 for pattern in JOB_POSTING_PATTERNS if re.search(pattern, normalized))
    receipt_or_invoice_count = sum(1 for pattern in RECEIPT_OR_INVOICE_PATTERNS if re.search(pattern, normalized))

    if receipt_or_invoice_count >= 3 and section_count < 2:
        raise_non_resume_error(
            "The extracted text appears to be a receipt, invoice, billing statement, or payment document rather than a resume.",
        )

    score = 0
    score += min(contact_count, 2) * 2
    score += min(section_count, 3) * 2
    score += 2 if date_count else 0
    score += 2 if career_term_count >= 2 else career_term_count
    score += 1 if bullet_count >= 3 else 0
    score += 1 if word_count >= 120 else 0
    score -= min(job_posting_count, 3) * 2
    score -= min(receipt_or_invoice_count, 3) * 2

    if score >= 5:
        return

    raise_non_resume_error(
        "The extracted text is missing enough resume-specific signals such as contact details, resume sections, roles, dates, skills, education, or work history.",
    )
