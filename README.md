# Resume Parser Service

FastAPI service for extracting structured resume data from uploaded PDF, DOCX, or TXT resumes. It extracts clean text, sends it to a pluggable LLM client, validates the response with Pydantic, and returns JSON ready for a later ATS-compliant resume generation service.

## Features

- `POST /api/resumes/parse` accepts `multipart/form-data`
- Supports `.pdf`, `.docx`, and `.txt`
- Configurable max upload size through `MAX_FILE_SIZE_MB`
- Text extraction with PyMuPDF and python-docx
- Clean whitespace and bullet normalization without stripping skill symbols like `C++`, `C#`, `.NET`, `Node.js`, or `CI/CD`
- Pluggable LLM provider abstraction for OpenAI, Azure OpenAI, or Ollama
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
| `LLM_PROVIDER` | `openai`, `azure_openai`, or `ollama` |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI chat model |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key |
| `AZURE_OPENAI_DEPLOYMENT` | Azure OpenAI deployment name |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI API version |
| `OLLAMA_BASE_URL` | Ollama server URL |
| `OLLAMA_MODEL` | Ollama model name |

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
      "headline": "Python Backend Engineer",
      "email": "alex@example.com",
      "phone": "+1 555 0100",
      "location": "Austin, TX",
      "linkedinUrl": "https://www.linkedin.com/in/alexmorgan",
      "portfolioUrl": null,
      "githubUrl": "https://github.com/alexmorgan",
      "otherLinks": []
    },
    "careerClassification": {
      "primaryFunction": "Backend Engineering",
      "industries": ["SaaS", "FinTech"],
      "seniorityLevel": "Senior",
      "yearsOfExperience": 8,
      "targetRoles": ["Senior Backend Engineer", "Python API Engineer"],
      "employmentTypeSignals": ["Full-time"]
    },
    "careerProgression": [],
    "professionalSummaryPoints": [
      "Backend engineer with experience building FastAPI services and cloud-native APIs."
    ],
    "coreSkills": ["Python", "FastAPI", "Docker", "PostgreSQL", "AWS"],
    "skillsMatrix": {
      "technicalSkills": [
        {
          "skill": "Python",
          "evidence": ["Built production API services"],
          "proficiencySignal": "Strong"
        }
      ],
      "domainSkills": [],
      "toolsAndPlatforms": [],
      "leadershipAndSoftSkills": [],
      "languages": []
    },
    "workExperience": [],
    "projectsOrCaseStudies": [],
    "achievementBank": [
      {
        "text": "Reduced API latency by 35%",
        "category": "Performance",
        "sourceRole": "Senior Backend Engineer",
        "quantified": true,
        "metrics": ["35%"],
        "rewritePotential": "high"
      }
    ],
    "education": [],
    "certificationsAndLicenses": [],
    "affiliationsAndMemberships": [],
    "awardsAndRecognition": [],
    "volunteerExperience": [],
    "publicationsAndSpeaking": [],
    "resumeBlocks": {
      "headlineOptions": ["Senior Python Backend Engineer"],
      "summaryBlock": ["Backend engineer focused on reliable, scalable API systems."],
      "skillsBlock": ["Python | FastAPI | Docker | AWS | PostgreSQL"],
      "experienceBlocks": [],
      "projectBlocks": [],
      "educationBlock": [],
      "certificationBlock": []
    },
    "recommendedResumeVariants": [
      {
        "variantName": "Backend API Engineer",
        "targetRole": "Senior Backend Engineer",
        "positioning": "Emphasize FastAPI, cloud services, and performance outcomes.",
        "sectionsToEmphasize": ["Skills", "Experience", "Projects"],
        "keywordsToInclude": ["FastAPI", "Docker", "REST APIs"]
      }
    ],
    "atsAnalysis": {
      "overallScore": 82,
      "parseReadiness": "Good",
      "formattingRisks": [],
      "keywordCoverage": ["Python", "FastAPI", "Docker"],
      "sectionCompleteness": ["Experience needs stronger metrics"],
      "recommendations": ["Add more quantified impact bullets"]
    },
    "jobFitAnalysis": {
      "fitScore": 78,
      "matchedRequirements": ["Python", "FastAPI", "Docker"],
      "partialMatches": ["Cloud experience"],
      "gaps": ["LLM integration not clearly stated"],
      "positioningAdvice": ["Bring API and deployment examples higher in the resume"]
    },
    "resumeStrengths": ["Clear backend engineering focus"],
    "missingOrWeakAreas": ["Some achievements lack metrics"],
    "atsKeywordsFound": ["Python", "FastAPI", "Docker"],
    "jobDescriptionKeywordMatches": ["Python", "FastAPI"],
    "jobDescriptionKeywordGaps": ["LLM integration"],
    "resumeGenerationStrategy": {
      "targetNarrative": "Position the candidate as a senior backend engineer for API-heavy roles.",
      "prioritySections": ["Summary", "Skills", "Experience"],
      "tone": "Concise and impact-focused",
      "contentRules": ["Do not invent missing metrics"],
      "rewriteFocusAreas": ["Quantified achievements", "Technical scope"],
      "atsOptimizationPlan": ["Add exact job keywords where truthfully supported"]
    },
    "safeRewriteSuggestions": [
      {
        "originalText": "Worked on APIs",
        "suggestedRewrite": "Built and maintained FastAPI services supporting production workflows.",
        "rationale": "Adds clarity without inventing metrics.",
        "confidence": "high"
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

