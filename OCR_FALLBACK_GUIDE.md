# OCR Fallback Feature Guide

## Overview

The resume parser API now includes OCR (Optical Character Recognition) fallback support for scanned/image-based PDFs. When normal text extraction fails or produces insufficient text, the system automatically attempts to extract text using OpenAI's vision model on page images.

## Architecture

### New Components

1. **`app/core/openai_vision_ocr_client.py`** - OpenAI Vision API Client
   - Converts PDF pages to images using PyMuPDF
   - Sends images to OpenAI vision model for text extraction
   - Handles base64 encoding and API communication

2. **`app/services/ocr_fallback_service.py`** - OCR Orchestrator
   - Manages the OCR extraction workflow
   - Converts multiple PDF pages to images
   - Merges extracted text from all pages in correct order
   - Handles page limits and DPI settings

3. **`app/services/document_text_extractor.py`** - Smart Text Extraction
   - Wraps existing text extraction logic
   - Implements intelligent fallback mechanism
   - Tracks extraction method (normal vs OCR)
   - Provides usability check for extracted text

### Updated Components

- **`app/core/config.py`** - Added OCR configuration settings
- **`app/services/text_extractor.py`** - Added `is_text_usable()` helper function
- **`app/api/routes_resume.py`** - Integrated new extraction flow with method tracking
- **`app/main.py`** - Added logging configuration

## Configuration

### Environment Variables

```env
# OCR Fallback Configuration
OCR_FALLBACK_ENABLED=true                 # Enable/disable OCR fallback
OCR_MIN_TEXT_LENGTH=300                   # Minimum characters for usable text
OCR_MODEL=gpt-4-vision                    # OpenAI vision model name
OCR_MAX_PAGES=5                           # Maximum PDF pages to process
OCR_DPI=200                               # Image DPI for PDF conversion
```

### Default Values (if not specified in .env)

| Setting | Default | Purpose |
|---------|---------|---------|
| `OCR_FALLBACK_ENABLED` | `true` | Whether OCR fallback is available |
| `OCR_MIN_TEXT_LENGTH` | `300` | Minimum characters for extracted text to be considered usable |
| `OCR_MODEL` | `gpt-4.1-mini` | OpenAI vision model for OCR |
| `OCR_MAX_PAGES` | `5` | Maximum pages to process (prevents excessive API calls) |
| `OCR_DPI` | `200` | Resolution for PDF-to-image conversion (higher = more detail, slower) |

## Extraction Flow

```
1. User uploads resume file
   ↓
2. Normal text extraction attempt
   ├─ PDF → PyMuPDF text extraction
   ├─ DOCX → python-docx parsing
   └─ TXT → UTF-8 decoding
   ↓
3. Text usability check
   ├─ Is text not null?
   ├─ Is text >= OCR_MIN_TEXT_LENGTH characters?
   └─ Is text.strip() non-empty?
   ↓
   ├─ YES → Use extracted text (extraction_method: "normal")
   │
   └─ NO → Check if OCR fallback possible
         ├─ OCR_FALLBACK_ENABLED?
         ├─ File is PDF?
         └─ YES → Proceed to OCR
   ↓
4. OCR Fallback (if triggered)
   ├─ Convert each PDF page to image (up to OCR_MAX_PAGES)
   ├─ For each image:
   │   ├─ Base64 encode image
   │   ├─ Send to OpenAI vision model
   │   └─ Extract and clean text
   ├─ Merge text from all pages in order
   └─ Use merged text (extraction_method: "ocr")
   ↓
5. Send final text to resume parser
   ↓
6. Return parsed resume with extraction method in metadata
```

## Response Metadata

The API response now includes extraction method information:

```json
{
  "id": "resume_123",
  "profile": { /* ... resume fields ... */ },
  "metadata": {
    "filename": "john_doe_resume.pdf",
    "fileType": ".pdf",
    "fileSizeBytes": 245000,
    "extractedTextCharacters": 5432,
    "jobDescriptionProvided": false,
    "extractionMethod": "normal|ocr"
  }
}
```

### Extraction Method Values

- **`"normal"`** - Text was extracted using traditional methods (PyMuPDF for PDF, python-docx for DOCX)
- **`"ocr"`** - Text was extracted using OpenAI vision model on page images

## Usage Examples

### Example 1: Scanned PDF (auto-triggers OCR)

```bash
curl -X POST http://localhost:8000/api/resumes/parse \
  -F "file=@scanned_resume.pdf"
```

**Result:** 
- Normal text extraction produces < 300 characters
- OCR fallback automatically triggers
- Response includes `"extractionMethod": "ocr"`

### Example 2: Text-based PDF (uses normal extraction)

```bash
curl -X POST http://localhost:8000/api/resumes/parse \
  -F "file=@normal_resume.pdf"
```

**Result:**
- Normal text extraction produces > 300 characters
- OCR fallback does NOT trigger
- Response includes `"extractionMethod": "normal"`

### Example 3: With job description

```bash
curl -X POST http://localhost:8000/api/resumes/parse \
  -F "file=@resume.pdf" \
  -F "jobDescription=Senior Python Developer with 5+ years experience"
```

**Result:** Same behavior as above, but parser receives job description context

## Logging

The implementation includes detailed logging for debugging and monitoring:

```
INFO - Normal text extraction completed: 5432 characters
DEBUG - Normal extraction produced sufficient text (5432 chars)
DEBUG - Converted PDF page 1 to image (DPI: 200)
DEBUG - Converted PDF page 2 to image (DPI: 200)
DEBUG - OCR extracted 2100 characters from page 1
DEBUG - OCR extracted 1800 characters from page 2
INFO - OCR extraction completed: 3900 total characters from 2 pages
INFO - OCR fallback succeeded: 3900 characters extracted
```

### Log Levels

- **INFO** - Major events (normal extraction, OCR triggered, OCR completed)
- **DEBUG** - Detailed information (page conversion, character counts)
- **WARNING** - Unexpected situations (insufficient text, OCR disabled)
- **ERROR** - Failures (PDF conversion error, API error, empty OCR result)

## Error Handling

### Normal Extraction Failures

If normal text extraction fails (corrupt/unreadable file):
- If OCR enabled and file is PDF → attempt OCR
- If OCR disabled or file is not PDF → return 422 error

```json
{
  "detail": "Could not read PDF resume. The file may be encrypted, corrupt, or image-only."
}
```

### OCR Failures

If OCR attempts fail:
- Invalid image format → 502 error
- OpenAI API error → 502 error
- Empty OCR result → Warning logged, empty text returned

```json
{
  "detail": "OpenAI vision API failed: ..."
}
```

## Performance Considerations

### API Call Costs

- **Normal extraction**: ~0.01¢ (PyMuPDF is local)
- **OCR fallback per page**: ~0.05¢-0.10¢ (OpenAI vision API call)
- **Max pages**: Default 5 pages = up to $0.50 per scanned resume

### Processing Time

- **Normal extraction**: <100ms
- **OCR fallback**: 5-15 seconds (image conversion + API calls)

### Optimization Tips

1. Set `OCR_MAX_PAGES` to reasonable limit (default 5)
2. Set `OCR_DPI` to balance quality vs processing time:
   - 150 DPI - Faster, acceptable for most resumes
   - 200 DPI - Default, good balance
   - 300 DPI - Slower, better for fine details
3. Monitor logs to identify which files trigger OCR

## Troubleshooting

### OCR not triggering on scanned PDF

**Check:**
1. Is `OCR_FALLBACK_ENABLED=true`?
2. What is `OCR_MIN_TEXT_LENGTH` value?
3. Does normal extraction produce any text?

**Debug:**
```bash
# Enable debug logging (set in main.py)
logging.getLogger().setLevel(logging.DEBUG)
```

### OCR producing poor results

**Solutions:**
1. Increase `OCR_DPI` (200 → 300)
2. Ensure scanned PDF has reasonable resolution
3. Check OpenAI API key validity
4. Verify network connectivity to OpenAI API

### High OCR costs

**Solutions:**
1. Reduce `OCR_MAX_PAGES` (5 → 3)
2. Use lower `OCR_DPI` (200 → 150)
3. Consider alternative OCR providers (AWS Textract, Google Vision)

## Future Enhancements

Possible improvements:

1. **Caching** - Cache OCR results for identical images
2. **Alternative OCR** - Support AWS Textract, Google Vision
3. **Language Support** - Multi-language OCR capability
4. **Layout Preservation** - Better handling of multi-column layouts
5. **Confidence Scoring** - Return confidence metrics for extracted text
6. **Selective Pages** - OCR only specific pages instead of first N

## Testing

### Manual Testing

```bash
# Test with scanned PDF
curl -X POST http://localhost:8000/api/resumes/parse \
  -F "file=@test_scanned.pdf" \
  -v

# Check metadata for extraction_method
cat response.json | jq '.metadata.extractionMethod'
```

### Unit Tests Example

```python
from app.services.document_text_extractor import is_text_usable

# Test the usability checker
assert is_text_usable("Hello world", 5) == True
assert is_text_usable("Hi", 5) == False
assert is_text_usable(None, 5) == False
assert is_text_usable("   ", 5) == False
```

## Integration with Existing Systems

The OCR fallback is fully backward compatible:

- **Existing API contracts** remain unchanged
- **Response structure** has optional new field
- **Normal extraction** unchanged for text-based documents
- **Database** can store extraction_method for analytics

### Database Migration (if needed)

If storing extraction_method in MongoDB:

```python
# Add to resume document schema
extracted_metadata = {
    "extraction_method": "normal|ocr",
    "extraction_date": datetime.now(),
    "extraction_dpi": 200,
    "ocr_pages": 3,
}
```

## Support & Maintenance

### Health Check Endpoint

```bash
curl http://localhost:8000/health
```

### Configuration Validation

On startup, the app validates:
- OPENAI_API_KEY is set
- OCR_MIN_TEXT_LENGTH is reasonable (10-1000)
- OCR_MAX_PAGES is reasonable (1-20)
- OCR_DPI is reasonable (100-400)

### Monitoring Recommendations

1. Track extraction_method distribution
2. Monitor OCR success rate
3. Log processing times
4. Alert on OCR API failures
5. Track cost per resume by extraction method
