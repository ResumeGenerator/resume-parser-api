SYSTEM_PROMPT = """You are an expert resume parser that extracts uploaded resume text into a strict JSON payload for a resume renderer.

CRITICAL RULES

1. Use ONLY information explicitly present in the resume.
2. Do NOT invent employers, job titles, dates, education, certifications, references, links, achievements, metrics, personal details, or skills.
3. If a field is missing, use an empty string, null, or an empty array according to the output shape.
4. Return VALID JSON ONLY.
5. Do not return markdown, comments, or explanatory text.
6. Use strings for phone and date fields. If multiple phone numbers are present, combine them into one comma-separated string.
7. Preserve the root keys exactly: template, format, data, font, color, withPhoto, avatar, contactsTitle, detailsTitle.
8. Preserve section object keys exactly: title, type, items.
9. Only include sections that are supported by the output JSON shape. Use these section types:
   * summary
   * experience
   * education
   * skill
   * course
   * language
   * reference
   * link
   * internship
   * hobby
10. Section titles should be human-readable, for example "Professional summary", "Work experience", "Education", and "Skills".
11. Dates should be copied in the clearest concise form present in the resume, such as "Jan 2024", "2021", or "Jan 2020 - Mar 2023".
12. If a Target Job Description is provided, do not add information from it to the resume. You may use it only to choose the most relevant existing summary wording, skills, and achievement ordering.

SECTION MAPPING

Professional summary:
* Put the best concise summary in data.summary.
* Also include a summary section with type "summary" and items as the same string when summary text exists.

Work experience:
* items must be an array of objects with position, company, location, jobType, reasonForLeaving, start, end, achievements.
* achievements must be an array of strings.

Education:
* items must be an array of objects with degree, school, faculty, department, location, years, start, end, highlights.
* highlights must be an array of strings.

Skills:
* items must be an array of objects with name and level.
* If skill proficiency is not stated, use an empty string for level.

Courses:
* items must be an array of objects with course, institution, start, end.

Languages:
* items must be an array of objects with language and level.
* If proficiency is not stated, use an empty string for level.

References:
* items must be an array of objects with name, company, email, phone.

Links:
* items must be an array of objects with label and link.

Internships:
* items must be an array of objects with position, company, location, start, end, achievements.

Hobbies:
* items must be an array of strings."""


USER_PROMPT_TEMPLATE = """INPUT

Resume Text:
{{RESUME_TEXT}}

Target Job Description:
{{JOB_DESCRIPTION}}

OUTPUT JSON

{
  "template": "strassburg",
  "format": "html",
  "data": {
    "name": "",
    "title": "",
    "location": "",
    "phone": "",
    "email": "",
    "summary": "",
    "dateOfBirth": "",
    "gender": "",
    "nationality": "",
    "documentDate": "",
    "address": "",
    "postalCode": "",
    "secondaryAddress": null,
    "sections": [
      {
        "title": "Professional summary",
        "type": "summary",
        "items": ""
      },
      {
        "title": "Work experience",
        "type": "experience",
        "items": [
          {
            "position": "",
            "company": "",
            "location": "",
            "jobType": "",
            "reasonForLeaving": "",
            "start": "",
            "end": "",
            "achievements": []
          }
        ]
      },
      {
        "title": "Education",
        "type": "education",
        "items": [
          {
            "degree": "",
            "school": "",
            "faculty": "",
            "department": "",
            "location": "",
            "years": "",
            "start": "",
            "end": "",
            "highlights": []
          }
        ]
      },
      {
        "title": "Skills",
        "type": "skill",
        "items": [
          {
            "name": "",
            "level": ""
          }
        ]
      },
      {
        "title": "Courses",
        "type": "course",
        "items": [
          {
            "course": "",
            "institution": "",
            "start": "",
            "end": ""
          }
        ]
      },
      {
        "title": "Languages",
        "type": "language",
        "items": [
          {
            "language": "",
            "level": ""
          }
        ]
      },
      {
        "title": "References",
        "type": "reference",
        "items": [
          {
            "name": "",
            "company": "",
            "email": "",
            "phone": ""
          }
        ]
      },
      {
        "title": "Links",
        "type": "link",
        "items": [
          {
            "label": "",
            "link": ""
          }
        ]
      },
      {
        "title": "Internships",
        "type": "internship",
        "items": [
          {
            "position": "",
            "company": "",
            "location": "",
            "start": "",
            "end": "",
            "achievements": []
          }
        ]
      },
      {
        "title": "Hobbies",
        "type": "hobby",
        "items": []
      }
    ]
  },
  "font": "Times New Roman",
  "color": "#000000",
  "withPhoto": false,
  "avatar": null,
  "contactsTitle": "Contacts",
  "detailsTitle": "Details"
}"""


def build_user_prompt(resume_text: str, job_description: str | None) -> str:
    return USER_PROMPT_TEMPLATE.replace("{{RESUME_TEXT}}", resume_text).replace(
        "{{JOB_DESCRIPTION}}",
        job_description or "",
    )
