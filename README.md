# Resume Parser Service

FastAPI service for extracting structured resume data from uploaded PDF, DOCX, or TXT resumes. It extracts clean text, sends it to a pluggable LLM client, validates the response with Pydantic, and returns JSON ready for a later ATS-compliant resume generation service.

## Features

- `POST /api/resumes/parse` accepts `multipart/form-data`
- `POST /api/resumes/{resume_id}/image` uploads a resume photo and stores its URL
- `POST /api/resumes/rephrase` accepts text and returns resume-ready rephrasing
- `POST /api/resumes/{resume_id}/edits` saves a single edited profile record per parsed resume
- Resume save and fetch endpoints accept optional `userId` ownership filtering
- Supports `.pdf`, `.docx`, and `.txt`
- Configurable max upload size through `MAX_FILE_SIZE_MB`
- Text extraction with PyMuPDF and python-docx
- Clean whitespace and bullet normalization without stripping skill symbols like `C++`, `C#`, `.NET`, `Node.js`, or `CI/CD`
- Rejects uploaded documents that do not appear to be resumes
- LLM integration through OpenAI
- OpenAI-backed resume text rephrasing with a dedicated prompt
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
| `PUBLIC_API_BASE_URL` | Public API origin used when generating avatar URLs, for example `https://resume-parser-api-staging.up.railway.app` |
| `MAX_FILE_SIZE_MB` | Maximum upload size in MB |
| `RESUME_IMAGE_MAX_SIZE_MB` | Maximum resume image upload size in MB |
| `RESUME_IMAGE_STORAGE_BACKEND` | `s3` for Railway bucket storage, or `local` for local filesystem storage |
| `S3_ENDPOINT_URL` | Railway S3-compatible endpoint URL |
| `S3_REGION` | Railway S3-compatible region, usually `auto` |
| `S3_BUCKET_NAME` | Railway bucket name |
| `S3_ACCESS_KEY_ID` | Railway bucket access key ID |
| `S3_SECRET_ACCESS_KEY` | Railway bucket secret access key |
| `RESUME_IMAGE_S3_KEY_PREFIX` | Optional S3 object prefix, default `resume-images` |
| `RESUME_IMAGE_STORAGE_DIR` | Local storage directory when `RESUME_IMAGE_STORAGE_BACKEND=local` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `LLM_PROVIDER` | `openai` |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI chat model |
| `MONGO_URI` | MongoDB connection URI; `MONGODB_URI` and `MONGO_URL` are also accepted |
| `MONGO_DATABASE` | MongoDB database name; `MONGO_DB` and `MONGODB_DATABASE` are also accepted |
| `MONGO_COLLECTION` | Collection for parsed resume documents; `MONGODB_RESUME_COLLECTION` is also accepted |
| `MONGO_EDITED_COLLECTION` | Collection for edited resume documents; `MONGODB_EDITED_RESUME_COLLECTION` is also accepted |

## Railway Deployment

Set these variables in Railway:

```text
OPENAI_API_KEY=...
LLM_PROVIDER=openai
MONGO_URI=...
MONGO_DATABASE=resume_parser
MONGO_COLLECTION=parsed_resumes
MONGO_EDITED_COLLECTION=edited_resumes
PUBLIC_API_BASE_URL=https://resume-parser-api-staging.up.railway.app
RESUME_IMAGE_STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://t3.storageapi.dev
S3_REGION=auto
S3_BUCKET_NAME=recorded-bottle-uayuz3vz5
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
RESUME_IMAGE_S3_KEY_PREFIX=resume-images
```

The Dockerfile uses Railway's `PORT` environment variable automatically:

```text
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

If your Railway MongoDB service exposes `MONGODB_URI` or `MONGO_URL`, the app will accept those too. For the Railway bucket shown in the service credentials tab, use the S3-compatible credential values for the `S3_*` variables.

## Example Request

```bash
curl -X POST "http://localhost:8000/api/resumes/parse" \
  -F "file=@/path/to/resume.pdf" \
  -F "userId=user-123" \
  -F "jobDescription=Senior Python Backend Engineer with FastAPI, cloud, Docker, and LLM integration experience."
```

Use `userId` as a multipart field when parsing a resume. For fetch/update operations, pass it as a query parameter, for example `GET /api/resumes?userId=user-123`, `GET /api/resumes/{resume_id}?userId=user-123`, or `POST /api/resumes/{resume_id}/edits?userId=user-123`.

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

The request may include a legacy `prompt` field from older clients, but the backend ignores it and always uses the server-side rephrase prompt.

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

The endpoint is intended for work experience bullets and professional summary text. It uses the separate `app/core/rephrase_prompt.py` prompt and validates the OpenAI JSON response before returning it.

## Upload Resume Image

Upload a JPEG, PNG, or WebP image for a saved resume:

```bash
curl -X POST "http://localhost:8000/api/resumes/675f3b5e9c8a6a1d2f3a4b5c/image?userId=user-123" \
  -F "file=@/path/to/photo.png"
```

The file is saved to the configured storage backend. With `RESUME_IMAGE_STORAGE_BACKEND=s3`, it is uploaded to the Railway S3-compatible bucket, and the returned resume includes:

```json
{
  "avatar": "http://localhost:8000/api/resumes/images/675f3b5e9c8a6a1d2f3a4b5c-abc123.png",
  "withPhoto": true
}
```

The same values are stored on the MongoDB resume document, and `GET /api/resumes/{resume_id}` returns them. The avatar URL points to the API image endpoint, which reads the object back from Railway storage.
Direct Railway bucket URLs such as `https://t3.storageapi.dev/<bucket>/<key>` can return `AccessDenied` because the bucket is private; use the `/api/resumes/images/{filename}` API URL instead.

## Example Response

```json
{
  "id": "675f3b5e9c8a6a1d2f3a4b5c",
  "resumeId": "675f3b5e9c8a6a1d2f3a4b5c",
  "userId": "user-123",
  "version": 1,
  "status": "parsed",
  "avatar": "",
  "withPhoto": false,
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
              "start": "01-01-2020",
              "end": "",
              "achievements": ["Built and maintained FastAPI services.", "Reduced API latency by 35%."]
            }
          ]
        },
        {
          "title": "Education",
          "type": "education",
          "items": [
            {
              "degree": "Bachelor of Science",
              "fieldOfStudy": "Computer Science",
              "school": "Example University",
              "faculty": "",
              "department": "",
              "location": "Austin, TX",
              "years": "2016 - 2020",
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
            { "name": "Python", "aiGenerated": false },
            { "name": "FastAPI", "aiGenerated": false },
            { "name": "Docker", "aiGenerated": true }
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
  "avatar": "",
  "withPhoto": false,
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
- Skill section items use `aiGenerated: false` for skills extracted from the resume and `aiGenerated: true` for AI-suggested skills.
- Education section items keep the credential in `degree` and the major, specialization, or discipline in `fieldOfStudy`.
- Template, style, photo, and renderer settings should be selected outside the parser response.
