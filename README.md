# Resume Parser Service

FastAPI service for extracting structured resume data from uploaded PDF, DOCX, or TXT resumes. It extracts clean text, sends it to a pluggable LLM client, validates the response with Pydantic, and returns JSON ready for a later ATS-compliant resume generation service.

## Features

- `POST /api/resumes/parse` accepts `multipart/form-data`
- `POST /api/resumes/rephrase` accepts text and returns resume-ready rephrasing
- Supports `.pdf`, `.docx`, and `.txt`
- Configurable max upload size through `MAX_FILE_SIZE_MB`
- Text extraction with PyMuPDF and python-docx
- Clean whitespace and bullet normalization without stripping skill symbols like `C++`, `C#`, `.NET`, `Node.js`, or `CI/CD`
- Rejects uploaded documents that do not appear to be resumes
- LLM integration through OpenAI or Gemini
- Gemini-backed resume text rephrasing with a dedicated prompt
- Pydantic validation for the parsed resume profile
- Stores parsed resume documents in MongoDB

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
    rephrase_prompt.py
    resume_prompt.py
  models/
    resume_schema.py
  services/
    text_extractor.py
    resume_parser.py
    resume_rephraser.py
    resume_repository.py
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
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `LLM_PROVIDER` | `openai` or `gemini` |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI chat model |
| `GEMINI_API_KEY` | Gemini API key; `GOOGLE_API_KEY` and `GOOGLE_GENERATIVE_AI_API_KEY` are also accepted |
| `GEMINI_MODEL` | Gemini model, defaults to `gemini-2.5-flash` |
| `MONGO_URI` | MongoDB connection URI; `MONGODB_URI` and `MONGO_URL` are also accepted |
| `MONGO_DATABASE` | MongoDB database name; `MONGO_DB` and `MONGODB_DATABASE` are also accepted |
| `MONGO_COLLECTION` | Collection for parsed resume documents; `MONGODB_RESUME_COLLECTION` is also accepted |

## Railway Deployment

Set these variables in Railway:

```text
OPENAI_API_KEY=...
LLM_PROVIDER=openai
MONGO_URI=...
MONGO_DATABASE=resume_parser
MONGO_COLLECTION=parsed_resumes
```

To use Gemini instead, set:

```text
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
```

The rephrase endpoint always uses Gemini, so `GEMINI_API_KEY` must be configured even when `LLM_PROVIDER=openai` for resume parsing.

The Dockerfile uses Railway's `PORT` environment variable automatically:

```text
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

If your Railway MongoDB service exposes `MONGODB_URI` or `MONGO_URL`, the app will accept those too.

## Example Request

```bash
curl -X POST "http://localhost:8000/api/resumes/parse" \
  -F "file=@/path/to/resume.pdf" \
  -F "jobDescription=Senior Python Backend Engineer with FastAPI, cloud, Docker, and LLM integration experience."
```

## Rephrase Resume Text

```bash
curl -X POST "http://localhost:8000/api/resumes/rephrase" \
  -H "Content-Type: application/json" \
  -d '{"text":"built APIs and fixed production bugs"}'
```

For multiline text, build the JSON with your HTTP client instead of manually interpolating a string:

```js
await fetch("http://localhost:8000/api/resumes/rephrase", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text }),
});
```

Multiline input is returned in the same structure: each line-separated or paragraph-separated text block is rephrased independently and joined back with the original line breaks.

Raw text is also accepted when sent as `text/plain`:

```bash
curl -X POST "http://localhost:8000/api/resumes/rephrase" \
  -H "Content-Type: text/plain" \
  --data-binary "built APIs
fixed production bugs"
```

Response:

```json
{
  "rephrasedText": "Built and maintained APIs while resolving production issues."
}
```

The endpoint is intended for work experience bullets and professional summary text. It uses the separate `app/core/rephrase_prompt.py` prompt and validates the Gemini JSON response before returning it.

## Example Response

```json
{
  "id": "675f3b5e9c8a6a1d2f3a4b5c",
  "resumeId": "675f3b5e9c8a6a1d2f3a4b5c",
  "version": 1,
  "status": "parsed",
  "profile": {
    "data": {
      "name": "Alex Morgan",
      "title": "Python Backend Engineer",
      "location": "Austin, TX",
      "phone": "+1 555 0100",
      "email": "alex@example.com",
      "summary": "Backend engineer with experience building FastAPI services and cloud-native APIs.",
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
          "items": ["Backend engineer with experience building FastAPI services and cloud-native APIs."]
        },
        {
          "title": "Work experience",
          "type": "experience",
          "items": [
            {
              "position": "Senior Backend Engineer",
              "company": "Example SaaS Co",
              "location": "Austin, TX",
              "jobType": "",
              "reasonForLeaving": "",
              "start": "2020",
              "end": "",
              "achievements": ["Built and maintained FastAPI services.", "Reduced API latency by 35%."]
            }
          ]
        },
        {
          "title": "Skills",
          "type": "skill",
          "items": [
            { "name": "Python", "level": "" },
            { "name": "FastAPI", "level": "" },
            { "name": "Docker", "level": "" }
          ]
        }
      ]
    }
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

## Mongo Storage

The parse endpoint persists the validated resume profile before returning it.

Stored MongoDB documents use this shape:

```json
{
  "_id": "ObjectId",
  "resumeId": "675f3b5e9c8a6a1d2f3a4b5c",
  "version": 1,
  "status": "parsed",
  "profile": {},
  "metadata": {},
  "source": {
    "jobDescription": "optional submitted job description"
  },
  "createdAt": "datetime",
  "updatedAt": "datetime"
}
```

## Future Resume Generation Usage

The returned JSON is intentionally shaped as parsed resume content for a downstream resume generation service:

- `data.name`, `data.title`, `data.location`, `data.phone`, `data.email`, and `data.summary` populate the resume header and summary.
- `data.sections` contains structured sections for summary, experience, education, skills, courses, languages, references, links, internships, and hobbies.
- Template, style, photo, and renderer settings should be selected outside the parser response.
