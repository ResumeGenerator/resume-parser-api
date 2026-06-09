# Resume Parser Service

FastAPI service for extracting structured resume data from uploaded PDF, DOCX, or TXT resumes. It extracts clean text, sends it to a pluggable LLM client, validates the response with Pydantic, and returns JSON ready for a later ATS-compliant resume generation service.

## Features

- `POST /api/resumes/parse` accepts `multipart/form-data`
- Supports `.pdf`, `.docx`, and `.txt`
- Configurable max upload size through `MAX_FILE_SIZE_MB`
- Text extraction with PyMuPDF and python-docx
- Clean whitespace and bullet normalization without stripping skill symbols like `C++`, `C#`, `.NET`, `Node.js`, or `CI/CD`
- Rejects uploaded documents that do not appear to be resumes
- LLM integration through OpenAI
- Pydantic validation for the parsed resume profile

## Project Structure

```text
resume-parser-service/
app/
  main.py
  api/
    routes_resume.py
  core/
    config.py
    llm_client.py
    resume_prompt.py
  models/
    resume_schema.py
  services/
    text_extractor.py
    resume_parser.py
  utils/
    text_cleaner.py
    file_validator.py
requirements.txt
Dockerfile
.env.example
README.md
```

## Local Run

```bash
cd resume-parser-service
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the API docs at:

```text
http://localhost:8000/docs
```

## Docker Run

```bash
cd resume-parser-service
docker build -t resume-parser-service .
docker run --env-file .env -p 8000:8000 resume-parser-service
```

## Environment Variables

| Variable | Description |
| --- | --- |
| `APP_NAME` | FastAPI app name |
| `MAX_FILE_SIZE_MB` | Maximum upload size in MB |
| `LLM_PROVIDER` | `openai` |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI chat model |

## Example Request

```bash
curl -X POST "http://localhost:8000/api/resumes/parse" \
  -F "file=@/path/to/resume.pdf" \
  -F "jobDescription=Senior Python Backend Engineer with FastAPI, cloud, Docker, and LLM integration experience."
```

## Example Response

```json
{
  "profile": {
    "candidateProfile": {
      "fullName": "Alex Morgan",
      "email": "alex@example.com",
      "phone": "+1 555 0100",
      "location": "Austin, TX",
      "currentTitle": "Python Backend Engineer",
      "professionalHeadline": "Backend engineer with FastAPI and cloud API experience",
      "totalExperienceYears": 8,
      "targetRole": null,
      "securityClearance": null,
      "visaStatusOrWorkAuthorization": null,
      "onlineProfiles": [
        {
          "platform": "LinkedIn",
          "url": "https://www.linkedin.com/in/alexmorgan"
        }
      ]
    },
    "careerClassification": {
      "industry": "Technology",
      "jobFamily": "Software Engineering",
      "subSpecialization": "Backend Engineering",
      "seniorityLevel": "Senior"
    },
    "careerProgression": {
      "careerLevel": "Senior",
      "industryFocus": ["SaaS", "FinTech"],
      "primarySpecialization": ["Backend APIs"],
      "secondarySpecialization": ["Cloud services"]
    },
    "professionalSummaryPoints": [
      "Backend engineer with experience building FastAPI services and cloud-native APIs."
    ],
    "coreSkills": {
      "hardSkills": ["Python", "REST APIs"],
      "toolsAndSoftware": ["Docker", "PostgreSQL"],
      "methodologiesAndFrameworks": ["Agile"],
      "industryKnowledge": ["SaaS"],
      "softSkills": ["Cross-functional collaboration"],
      "languages": []
    },
    "skillsMatrix": {
      "programmingLanguages": ["Python"],
      "frameworks": ["FastAPI"],
      "cloudPlatforms": ["AWS"],
      "databases": ["PostgreSQL"],
      "devOpsTools": ["Docker"],
      "testingTools": [],
      "businessTools": [],
      "industryTools": []
    },
    "workExperience": [
      {
        "companyOrOrganization": "Example SaaS Co",
        "role": "Senior Backend Engineer",
        "location": "Austin, TX",
        "startDate": "2020",
        "endDate": null,
        "isCurrent": true,
        "employmentType": null,
        "managementLevel": null,
        "responsibilities": ["Built and maintained FastAPI services."],
        "achievements": ["Reduced API latency by 35%."],
        "toolsAndTaxonomiesUsed": ["Python", "FastAPI", "Docker"],
        "keywordsExtracted": ["Python", "FastAPI", "REST APIs"],
        "industryOrDomain": "SaaS"
      }
    ],
    "projectsOrCaseStudies": [],
    "achievementBank": [
      {
        "achievement": "Reduced API latency by 35%",
        "category": "Performance",
        "sourceCompany": "Example SaaS Co",
        "year": null
      }
    ],
    "education": [],
    "certificationsAndLicenses": [],
    "affiliationsAndMemberships": [],
    "awardsAndRecognition": [],
    "volunteerExperience": [],
    "publicationsAndSpeaking": [],
    "resumeBlocks": {
      "executiveSummary": ["Backend engineer focused on reliable, scalable API systems."],
      "technicalHighlights": ["Python, FastAPI, Docker, AWS, PostgreSQL"],
      "leadershipHighlights": [],
      "projectHighlights": [],
      "industryHighlights": ["SaaS API platforms"]
    },
    "recommendedResumeVariants": [
      {
        "name": "Backend API Engineer",
        "confidence": 0.86
      }
    ],
    "atsAnalysis": {
      "estimatedAtsScore": 82,
      "keywordDensity": [
        {
          "keyword": "Python",
          "count": 4
        }
      ],
      "missingCriticalSections": [],
      "formattingRisks": [],
      "duplicateSkills": []
    },
    "jobFitAnalysis": {
      "matchPercentage": 78,
      "strongMatches": ["Python", "FastAPI", "Docker"],
      "partialMatches": ["Cloud experience"],
      "missingRequirements": ["LLM integration"]
    },
    "resumeStrengths": ["Clear backend engineering focus"],
    "missingOrWeakAreas": ["Some achievements lack metrics"],
    "atsKeywordsFound": ["Python", "FastAPI", "Docker"],
    "jobDescriptionKeywordMatches": ["Python", "FastAPI"],
    "jobDescriptionKeywordGaps": ["LLM integration"],
    "resumeGenerationStrategy": {
      "standardAtsVersion": ["Prioritize summary, skills, and experience sections."],
      "performanceAndMetricsDrivenVersion": ["Emphasize the stated 35% latency reduction."],
      "leadershipOrSpecialistVersion": [],
      "functionalOrCareerChangeVersion": []
    },
    "safeRewriteSuggestions": [
      {
        "category": "Experience bullet",
        "originalPoint": "Worked on APIs",
        "improvedPoint": "Built and maintained FastAPI services supporting production workflows.",
        "reason": "Adds clarity without inventing metrics."
      }
    ]
  },
  "metadata": {
    "filename": "resume.pdf",
    "fileType": ".pdf",
    "fileSizeBytes": 184320,
    "extractedTextCharacters": 6421,
    "jobDescriptionProvided": true
  }
}
```

## Future Resume Generation Usage

The returned JSON is intentionally shaped for a downstream resume generation service:

- `candidateProfile`, `education`, and `certificationsAndLicenses` can populate fixed resume sections.
- `achievementBank` gives reusable impact bullets that can be selected per target role.
- `resumeBlocks` provides prebuilt blocks for headline, summary, skills, projects, and experience sections.
- `recommendedResumeVariants` can drive different generated versions for different target roles.
- `atsAnalysis`, keyword matches, and keyword gaps can guide ATS optimization before rendering DOCX/PDF.
- `safeRewriteSuggestions` identifies truthful improvements without fabricating responsibilities, credentials, or metrics.
