# OCR Fallback - Quick Start Guide

## What's New

Your resume parser API now has **automatic OCR fallback support** for scanned/image-based PDFs. When normal text extraction fails or produces insufficient text, the system automatically extracts text using OpenAI's vision model on page images.

## Installation

1. **Update dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment variables are ready** in `.env`:
   ```env
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   OCR_FALLBACK_ENABLED=true
   OCR_MIN_TEXT_LENGTH=300
   OCR_MODEL=gpt-4.1-mini
   OCR_MAX_PAGES=5
   OCR_DPI=200
   PUBLIC_API_BASE_URL=https://resume-parser-api-staging.up.railway.app
   RESUME_IMAGE_STORAGE_BACKEND=s3
   S3_ENDPOINT_URL=https://t3.storageapi.dev
   S3_REGION=auto
   S3_BUCKET_NAME=recorded-bottle-uayuz3vz5
   S3_ACCESS_KEY_ID=...
   S3_SECRET_ACCESS_KEY=...
   ```

   Resume parsing, rephrasing, and OCR fallback all use OpenAI, so `OPENAI_API_KEY` is required for normal operation.
   Resume image uploads are saved to the configured Railway S3-compatible bucket.

## How It Works

```
User uploads PDF
    ↓
Normal text extraction (PyMuPDF)
    ↓
Is text >= 300 characters?
    ├─ YES → Use extracted text
    └─ NO → Convert PDF pages to images
           → Send to OpenAI vision model
           → Extract and merge text from all pages
           → Use OCR text
    ↓
Parse with configured LLM provider
    ↓
Return response with extraction_method: "normal" or "ocr"
```

## Testing

### Test 1: Text-based PDF (uses normal extraction)
```bash
curl -X POST http://localhost:8000/api/resumes/parse \
  -F "file=@normal_resume.pdf"

# Result: "extractionMethod": "normal"
```

### Test 2: Scanned PDF (auto-triggers OCR)
```bash
curl -X POST http://localhost:8000/api/resumes/parse \
  -F "file=@scanned_resume.pdf"

# Result: "extractionMethod": "ocr"
```

### Test 3: With job description
```bash
curl -X POST http://localhost:8000/api/resumes/parse \
  -F "file=@resume.pdf" \
  -F "jobDescription=Senior Python Developer"

# Result includes job matching based on OCR text if needed
```

## Configuration

### Key Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `OCR_FALLBACK_ENABLED` | `true` | Enable/disable OCR fallback |
| `OCR_MIN_TEXT_LENGTH` | `300` | Minimum chars for usable text |
| `OCR_MODEL` | `gpt-4.1-mini` | Vision model for OCR |
| `OCR_MAX_PAGES` | `5` | Max pages to process (limits API calls) |
| `OCR_DPI` | `200` | Image quality (higher = better but slower) |

### Adjust for Your Needs

**For faster processing, lower costs**:
```env
OCR_MIN_TEXT_LENGTH=500    # Fewer OCR triggers
OCR_MAX_PAGES=3             # Fewer API calls
OCR_DPI=150                 # Lower quality but faster
```

**For better accuracy**:
```env
OCR_MIN_TEXT_LENGTH=100    # More OCR fallbacks
OCR_MAX_PAGES=10           # Process all pages
OCR_DPI=300                # Higher quality
```

## Response Format

The API response now includes extraction metadata:

```json
{
  "id": "resume_12345",
  "profile": {
    "template": "strassburg",
    "format": "html",
    "data": {
      "name": "John Doe",
      "title": "Software Engineer",
      "email": "john@example.com",
      "phone": "+1-555-0000",
      "sections": [ /* renderer-ready resume sections */ ]
    },
    "font": "Times New Roman",
    "color": "#000000",
    "withPhoto": false,
    "avatar": null,
    "contactsTitle": "Contacts",
    "detailsTitle": "Details"
  },
  "metadata": {
    "filename": "john_doe_resume.pdf",
    "fileType": ".pdf",
    "fileSizeBytes": 245000,
    "extractedTextCharacters": 5432,
    "jobDescriptionProvided": false,
    "extractionMethod": "normal|ocr"  // NEW FIELD
  }
}
```

## Logging

Watch the logs to see OCR in action:

```bash
# Terminal 1: Run application
python -m uvicorn app.main:app --reload

# Terminal 2: Upload a scanned PDF and watch logs
curl -X POST http://localhost:8000/api/resumes/parse \
  -F "file=@scanned_resume.pdf"

# Expected logs:
# INFO - Normal text extraction completed: 50 characters
# INFO - Normal extraction insufficient (50 < 300 chars). Attempting OCR fallback.
# DEBUG - Converted PDF page 1 to image (DPI: 200)
# DEBUG - OCR extracted 2100 characters from page 1
# INFO - OCR extraction completed: 2100 total characters from 1 pages
# INFO - OCR fallback succeeded: 2100 characters extracted
```

## Architecture

### New Files
- **`app/core/openai_vision_ocr_client.py`** - Handles OpenAI vision API calls
- **`app/services/ocr_fallback_service.py`** - Orchestrates OCR extraction
- **`app/services/document_text_extractor.py`** - Smart extraction with fallback

### Updated Files
- **`app/core/config.py`** - OCR configuration
- **`app/api/routes_resume.py`** - Integrated extraction with method tracking
- **`app/main.py`** - Logging setup
- **`requirements.txt`** - Added Pillow dependency
- **`.env`** - OCR configuration variables

## Production Deployment

### Docker
```bash
# Build with new dependencies
docker build -t resume-parser:ocr .

# Run with OCR config
docker run -p 8000:8000 \
  -e OCR_FALLBACK_ENABLED=true \
  -e OPENAI_API_KEY=sk-... \
  -e MONGO_COLLECTION=parsed_resumes \
  -e PUBLIC_API_BASE_URL=https://resume-parser-api-staging.up.railway.app \
  -e RESUME_IMAGE_STORAGE_BACKEND=s3 \
  -e S3_ENDPOINT_URL=https://t3.storageapi.dev \
  -e S3_REGION=auto \
  -e S3_BUCKET_NAME=recorded-bottle-uayuz3vz5 \
  -e S3_ACCESS_KEY_ID=... \
  -e S3_SECRET_ACCESS_KEY=... \
  resume-parser:ocr
```

### Docker Compose
```bash
docker-compose up -d  # Uses updated docker-compose.yml with OCR vars
```

### Kubernetes
See `DEPLOYMENT_DOCKER_GUIDE.md` for K8s manifests

## Common Use Cases

### Scenario 1: Client uploads text-based PDF
- ✓ Normal extraction: 5000+ characters
- → Uses normal extraction
- → Fast (< 1 second)
- → No OCR API calls, no extra cost

### Scenario 2: Client uploads scanned/image PDF
- ✓ Normal extraction: 50-100 characters (mostly garbage)
- → Triggers OCR fallback
- → Slower (5-15 seconds)
- → Uses OpenAI vision API (slight cost)
- → Gets clean extracted text

### Scenario 3: Client uploads DOCX
- ✓ Normal extraction: 3000+ characters
- → Uses normal extraction
- → Fast (< 1 second)
- → OCR not triggered (only for PDFs)

### Scenario 4: Disable OCR fallback (on budget)
```env
OCR_FALLBACK_ENABLED=false
```
- → Only uses normal extraction
- → No OCR API calls, no extra cost
- → Scanned PDFs will return empty/minimal text

## Troubleshooting

### OCR not working?

1. **Check if enabled**:
   ```bash
   grep OCR_FALLBACK_ENABLED .env
   # Should be: OCR_FALLBACK_ENABLED=true
   ```

2. **Check API key**:
   ```bash
   grep OPENAI_API_KEY .env
   # Should have valid key starting with sk-
   ```

3. **Check logs**:
   ```bash
   # Look for error messages
   grep -i "error\|failed" app.log
   ```

4. **Test OpenAI connectivity**:
   ```bash
   python -c "import openai; print('OK')"
   ```

### Poor OCR quality?

- Increase `OCR_DPI`: 200 → 300
- Ensure scanned PDF has reasonable resolution
- Check image quality in original file

### High costs?

- Reduce `OCR_MAX_PAGES`: 5 → 3
- Reduce `OCR_DPI`: 200 → 150
- Increase `OCR_MIN_TEXT_LENGTH`: 300 → 500

## Cost Estimation

- **Normal PDF**: ~$0 (no OCR)
- **Scanned PDF (3 pages)**: ~$0.03-0.09 (OpenAI vision API)

For 1000 scanned resumes:
- At $0.05 per resume = $50/month
- At 5 pages per resume = $250/month (if all scanned)

## Performance

| Operation | Time | Cost |
|-----------|------|------|
| Normal extraction | <100ms | $0 |
| OCR fallback (3 pages) | 10-15s | $0.05 |
| Full parsing (normal) | 1-2s | $0.01 |
| Full parsing (with OCR) | 12-18s | $0.06 |

## Next Steps

1. **Test with sample PDFs**:
   - Upload a text-based PDF → should use normal
   - Upload a scanned PDF → should use OCR

2. **Monitor extraction methods**:
   - Check metadata in saved resumes
   - Track "extractionMethod" distribution
   - Optimize settings based on patterns

3. **Adjust configuration**:
   - Set OCR_MIN_TEXT_LENGTH based on your resume quality
   - Set OCR_MAX_PAGES based on budget
   - Set OCR_DPI based on speed needs

4. **Integrate with your UI**:
   - Show extraction method to users
   - Warn when OCR is used (might take longer)
   - Track OCR usage for analytics

## Documentation Files

- **`OCR_FALLBACK_GUIDE.md`** - Comprehensive technical guide
- **`DEPLOYMENT_DOCKER_GUIDE.md`** - Docker/K8s deployment instructions
- **`tests_ocr_examples.py`** - Unit test examples
- **`QUICKSTART.md`** - This file

## Support

For issues or questions:
1. Check logs: `grep OCR app.log`
2. Review `OCR_FALLBACK_GUIDE.md` troubleshooting section
3. Verify configuration in `.env`
4. Check OpenAI API key validity
5. Ensure network access to `api.openai.com`

---

**You're all set!** Your resume parser now has intelligent OCR fallback for scanned PDFs. 🚀
