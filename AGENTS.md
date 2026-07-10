# AGENTS.md

Guidance for Codex or other coding agents working in this repository.

## Project Overview

This repository is a FastAPI backend for parsing resumes into structured JSON. It accepts uploaded PDF, DOCX, or TXT files, extracts text, rejects documents that do not look like resumes, sends resume text to an OpenAI-backed LLM client, validates the response with strict Pydantic models, and stores parsed documents in MongoDB.

The parsed output is intentionally shaped for a downstream resume generation UI/service. Preserve the response contract unless the task explicitly asks for a schema change.

## Tech Stack

- Python 3.11
- FastAPI and Uvicorn
- Pydantic v2 and pydantic-settings
- Motor async MongoDB client
- PyMuPDF for PDF text extraction
- python-docx for DOCX extraction
- httpx for OpenAI API calls
- Pillow and OpenAI vision flow for OCR fallback
- unittest-based tests under `tests/`

## Important Entry Points

- `app/main.py`: FastAPI app construction, CORS, lifespan startup/shutdown, health routes, router registration.
- `app/api/routes_resume.py`: HTTP API for parsing, listing, fetching, and updating resume images.
- `app/core/config.py`: environment-backed settings and aliases.
- `app/core/llm_client.py`: LLM abstraction and OpenAI chat-completions implementation.
- `app/core/resume_prompt.py`: prompt contract for structured resume extraction.
- `app/core/database.py`: global Mongo repository lifecycle.
- `app/models/resume_schema.py`: canonical API response schema. Models forbid extra fields.
- `app/services/document_text_extractor.py`: normal text extraction plus OCR fallback orchestration.
- `app/services/text_extractor.py`: PDF/DOCX/TXT extraction helpers.
- `app/services/ocr_fallback_service.py`: PDF page rendering and OCR fallback.
- `app/services/resume_parser.py`: calls the LLM client and validates/normalizes the profile.
- `app/services/resume_repository.py`: Mongo persistence and serialization.
- `app/utils/file_validator.py`: upload extension and size validation.
- `app/utils/resume_detector.py`: heuristic rejection of non-resume documents.

## API Surface

- `GET /`: liveness response.
- `GET /health`: health response.
- `POST /api/resumes/parse`: multipart upload endpoint.
  - Form file field: `file`
  - Optional form field: `jobDescription`
  - Returns `ResumeParseResponse`
  - Persists the parsed profile before returning.
- `GET /api/resumes`: list saved resume summaries.
  - Query params: `limit` from 1 to 500, `skip` >= 0.
- `GET /api/resumes/{resume_id}`: fetch a parsed resume by its stable ID.

## Runtime Configuration

Settings are loaded from environment variables and `.env` through `app/core/config.py`.

Required for normal parse flow:

- `OPENAI_API_KEY`
- `MONGO_URI` or `MONGODB_URI` or `MONGO_URL`

Common optional settings:

- `APP_NAME`
- `MAX_FILE_SIZE_MB`
- `CORS_ORIGINS`
- `LLM_PROVIDER`, currently only `openai`
- `OPENAI_MODEL`, default `gpt-4.1-mini`
- `OCR_FALLBACK_ENABLED`, default `true`
- `OCR_MIN_TEXT_LENGTH`, default `300`
- `OCR_MODEL`, default `gpt-4.1-mini`
- `OCR_MAX_PAGES`, default `5`
- `OCR_DPI`, default `200`
- `MONGO_DATABASE` or `MONGO_DB` or `MONGODB_DATABASE`
- `MONGO_COLLECTION` or `MONGODB_RESUME_COLLECTION`

Do not hardcode secrets. Use `.env.example` for documenting new variables.

## Local Commands

Create and install:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests:

```bash
python -m unittest discover -s tests
```

Run with Docker Compose:

```bash
docker compose up --build
```

Note: `docker-compose.yml` expects the external Docker network `resume-parser-dev` to exist.

## Coding Rules For Agents

- Keep changes small and aligned with the existing module boundaries.
- Preserve async behavior in FastAPI routes and Mongo repository methods.
- Use dependency injection via FastAPI `Depends` for settings where routes already do so.
- Keep `ResumeProfile` and response models strict. If adding fields, update:
  - `app/models/resume_schema.py`
  - `app/core/resume_prompt.py`
  - tests in `tests/`
  - README/example response if the public contract changes.
- Treat LLM output as untrusted. Validate and normalize before returning or storing.
- Do not bypass `read_and_validate_file`, `DocumentTextExtractor`, or `validate_resume_document` in the parse flow.
- Do not introduce database writes before validation succeeds.
- Keep Mongo serialization JSON-safe. Convert `ObjectId` and `datetime` values before returning API responses.
- Preserve stable parsed-resume IDs unless explicitly asked to change them.
- Avoid adding broad dependencies. Prefer small standard-library or existing-stack solutions.

## Testing Expectations

At minimum, run:

```bash
python -m unittest discover -s tests
```

Add or update tests when changing:

- Pydantic schema behavior or validators.
- LLM payload normalization.
- File validation rules.
- Resume detection heuristics.
- Mongo document serialization.
- API response shape.

For changes that touch OCR, extraction, OpenAI calls, or MongoDB, add focused unit tests where possible and document any external integration tests that could not be run locally.

## Known Implementation Notes

- `app/models/resume_schema.py` uses `extra="forbid"`, so unexpected LLM keys cause validation errors.
- `totalExperienceYears` accepts strings like `8+`, `10 years`, and `10.5 years` through normalizers.
- OCR fallback is only attempted for PDFs when normal extraction fails or produces less text than `OCR_MIN_TEXT_LENGTH`.
- `POST /api/resumes/parse` returns `503` when MongoDB is not configured because parsed resumes are persisted as part of the request.
- The OpenAI client currently uses `/v1/chat/completions` with `response_format={"type": "json_object"}`.
- The Dockerfile uses Railway-style `${PORT:-8000}` at runtime.

## Documentation To Keep In Sync

- `README.md`: public overview, API examples, environment variables.
- `.env.example`: new or changed environment variables.
- `QUICKSTART.md`, `DEPLOYMENT_DOCKER_GUIDE.md`, and `OCR_FALLBACK_GUIDE.md`: update when behavior affects setup, deployment, or OCR.
- `IMPLEMENTATION_SUMMARY.md`: update only when the user asks for a broader project summary refresh.
