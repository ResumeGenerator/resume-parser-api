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
- Stores parsed resume documents in MongoDB
- Stores rendered/template resume payloads in MongoDB
- Lists saved resume summaries for UI binding

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
| `LLM_PROVIDER` | `openai` |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI chat model |
| `MONGO_URI` | MongoDB connection URI; `MONGODB_URI` and `MONGO_URL` are also accepted |
| `MONGO_DATABASE` | MongoDB database name; `MONGO_DB` and `MONGODB_DATABASE` are also accepted |
| `MONGO_COLLECTION` | Collection for parsed and edited resume versions; `MONGODB_RESUME_COLLECTION` is also accepted |
| `MONGO_TEMPLATE_COLLECTION` | Collection for rendered/template resume payloads; `MONGODB_TEMPLATE_RESUME_COLLECTION` is also accepted |

## Railway Deployment

Set these variables in Railway:

```text
OPENAI_API_KEY=...
MONGO_URI=...
MONGO_DATABASE=resume_parser
MONGO_COLLECTION=parsed_resumes
MONGO_TEMPLATE_COLLECTION=template_resumes
```

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

## Example Response

```json
{
  "id": "675f3b5e9c8a6a1d2f3a4b5c",
  "resumeId": "675f3b5e9c8a6a1d2f3a4b5c",
  "version": 1,
  "status": "parsed",
  "profile": {
    "template": "strassburg",
    "format": "html",
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
          "items": "Backend engineer with experience building FastAPI services and cloud-native APIs."
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
    },
    "font": "Times New Roman",
    "color": "#000000",
    "withPhoto": false,
    "avatar": null,
    "contactsTitle": "Contacts",
    "detailsTitle": "Details"
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

## Fetch Stored Resume

List saved resume summaries:

```bash
curl "http://localhost:8000/api/resumes"
```

Fetch a full saved resume by ID:

```bash
curl "http://localhost:8000/api/resumes/675f3b5e9c8a6a1d2f3a4b5c"
```

Save a rendered/template resume payload for a parsed resume:

```bash
curl -X POST "http://localhost:8000/api/resumes/675f3b5e9c8a6a1d2f3a4b5c/templates" \
  -H "Content-Type: application/json" \
  -d '{
    "template": "sydney",
    "format": "html",
    "data": {
      "name": "Biju Manayagaths",
      "title": "Solution Architect",
      "location": "Doha, Qatar",
      "phone": "+97474452435",
      "email": "bijum777@gmail.com",
      "summary": "Senior Engineer with expertise in designing scalable system architectures.",
      "sections": []
    },
    "font": "Arial",
    "color": "#000000",
    "withPhoto": true,
    "avatar": "https://example.com/avatar.png",
    "contactsTitle": "Contacts",
    "detailsTitle": "Details"
  }'
```

The `POST /api/resumes/{resume_id}/templates` and `POST /api/resumes/{resume_id}/edits` responses include `previewHtml` so the UI can immediately render the saved or edited resume preview.

Fetch the latest rendered/template resume payload:

```bash
curl "http://localhost:8000/api/resumes/675f3b5e9c8a6a1d2f3a4b5c/templates/latest"
```

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

Template resume MongoDB documents use this shape:

```json
{
  "_id": "ObjectId",
  "originalResumeId": "675f3b5e9c8a6a1d2f3a4b5c",
  "templateResume": {},
  "metadata": {},
  "source": {},
  "createdAt": "datetime",
  "updatedAt": "datetime"
}
```

## Future Resume Generation Usage

The returned JSON is intentionally shaped for a downstream resume generation service:

- Root fields such as `template`, `format`, `font`, `color`, `withPhoto`, `contactsTitle`, and `detailsTitle` can be passed directly to the renderer.
- `data.name`, `data.title`, `data.location`, `data.phone`, `data.email`, and `data.summary` populate the resume header and summary.
- `data.sections` contains renderer-ready sections for summary, experience, education, skills, courses, languages, references, links, internships, and hobbies.
- Section `items` are shaped for the renderer and remain strict at the top-level API boundary.
