"""
Example tests for OCR fallback functionality.
Place these tests in tests/ directory and run with: pytest tests/test_ocr_fallback.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.text_extractor import is_text_usable
from app.services.document_text_extractor import DocumentTextExtractor
from app.core.config import Settings
from app.core.openai_vision_ocr_client import OpenAIVisionOCRClient


class TestIsTextUsable:
    """Tests for text usability checker."""

    def test_valid_text(self):
        """Test that sufficient text is marked as usable."""
        assert is_text_usable("Hello world", 5) is True
        assert is_text_usable("This is a longer text with many words", 10) is True

    def test_empty_text(self):
        """Test that empty text is not usable."""
        assert is_text_usable("", 5) is False
        assert is_text_usable("   ", 5) is False
        assert is_text_usable("\n\n", 5) is False

    def test_none_text(self):
        """Test that None is not usable."""
        assert is_text_usable(None, 5) is False

    def test_below_minimum_length(self):
        """Test that text below minimum length is not usable."""
        assert is_text_usable("Hi", 5) is False
        assert is_text_usable("Test", 10) is False

    def test_whitespace_stripped(self):
        """Test that whitespace is stripped when checking length."""
        assert is_text_usable("   Hello   ", 5) is True
        assert is_text_usable("   Hi   ", 5) is False


class TestOpenAIVisionOCRClient:
    """Tests for OpenAI vision OCR client."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(spec=Settings)
        settings.openai_api_key = "test-api-key"
        settings.ocr_model = "gpt-4-vision"
        settings.ocr_dpi = 200
        settings.ocr_max_pages = 5
        return settings

    def test_init_without_api_key(self):
        """Test that initialization fails without API key."""
        settings = MagicMock(spec=Settings)
        settings.openai_api_key = None

        with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
            OpenAIVisionOCRClient(settings)

    def test_init_with_api_key(self, mock_settings):
        """Test successful initialization with API key."""
        client = OpenAIVisionOCRClient(mock_settings)
        assert client.api_key == "test-api-key"
        assert client.model == "gpt-4-vision"

    @patch("httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_extract_text_from_image_success(self, mock_async_client, mock_settings):
        """Test successful image text extraction."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Extracted text from resume image"
                    }
                }
            ]
        }

        mock_async_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        client = OpenAIVisionOCRClient(mock_settings)
        result = await client.extract_text_from_image(b"image_data")

        assert result == "Extracted text from resume image"

    @patch("httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_extract_text_from_image_api_error(self, mock_async_client, mock_settings):
        """Test handling of API error."""
        from fastapi import HTTPException

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_async_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        client = OpenAIVisionOCRClient(mock_settings)

        with pytest.raises(HTTPException) as exc_info:
            await client.extract_text_from_image(b"image_data")

        assert exc_info.value.status_code == 502


class TestDocumentTextExtractor:
    """Tests for document text extractor with OCR fallback."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(spec=Settings)
        settings.openai_api_key = "test-api-key"
        settings.ocr_fallback_enabled = True
        settings.ocr_min_text_length = 300
        settings.ocr_model = "gpt-4-vision"
        settings.ocr_dpi = 200
        settings.ocr_max_pages = 5
        return settings

    @pytest.mark.asyncio
    @patch("app.services.document_text_extractor.extract_resume_text")
    @patch("app.services.document_text_extractor.run_in_threadpool")
    async def test_extract_with_sufficient_text(self, mock_run, mock_extract, mock_settings):
        """Test extraction when normal extraction produces sufficient text."""
        mock_run.return_value = "This is a long resume text with more than 300 characters" * 10

        extractor = DocumentTextExtractor(settings=mock_settings)
        text, method = await extractor.extract_with_fallback(b"pdf_content", ".pdf")

        assert len(text) > 300
        assert method == "normal"

    @pytest.mark.asyncio
    @patch("app.services.document_text_extractor.extract_resume_text")
    @patch("app.services.document_text_extractor.run_in_threadpool")
    @patch("app.services.document_text_extractor.OCRFallbackService")
    async def test_extract_triggers_ocr_on_insufficient_text(
        self, mock_ocr_service_class, mock_run, mock_extract, mock_settings
    ):
        """Test that OCR is triggered when normal extraction produces insufficient text."""
        # Normal extraction produces too little text
        mock_run.side_effect = ["Short text"]

        # Mock OCR service
        mock_ocr_service = AsyncMock()
        mock_ocr_service.extract_text_from_pdf_via_ocr = AsyncMock(
            return_value="OCR extracted text" * 50
        )
        mock_ocr_service_class.return_value = mock_ocr_service

        extractor = DocumentTextExtractor(settings=mock_settings)
        text, method = await extractor.extract_with_fallback(b"pdf_content", ".pdf")

        assert method == "ocr"
        assert len(text) > 300

    @pytest.mark.asyncio
    @patch("app.services.document_text_extractor.extract_resume_text")
    @patch("app.services.document_text_extractor.run_in_threadpool")
    async def test_ocr_disabled_returns_normal_text(self, mock_run, mock_extract, mock_settings):
        """Test that OCR is not triggered when disabled."""
        mock_settings.ocr_fallback_enabled = False
        mock_run.return_value = "Short text"

        extractor = DocumentTextExtractor(settings=mock_settings)
        text, method = await extractor.extract_with_fallback(b"pdf_content", ".pdf")

        assert method == "normal"
        assert text == "Short text"

    @pytest.mark.asyncio
    @patch("app.services.document_text_extractor.extract_resume_text")
    @patch("app.services.document_text_extractor.run_in_threadpool")
    async def test_ocr_not_triggered_for_docx(self, mock_run, mock_extract, mock_settings):
        """Test that OCR is not triggered for DOCX files."""
        mock_run.return_value = "Short text"

        extractor = DocumentTextExtractor(settings=mock_settings)
        text, method = await extractor.extract_with_fallback(b"docx_content", ".docx")

        assert method == "normal"
        assert text == "Short text"


# Integration test example
@pytest.mark.asyncio
async def test_full_parsing_flow_with_ocr():
    """Integration test for full parsing flow with OCR fallback."""
    # This would test the entire flow from API endpoint to response
    # Requires actual test files and full application setup
    pass


# Manual testing functions (not pytest, for direct execution)
def manual_test_text_usability():
    """Manual test for text usability checker."""
    test_cases = [
        ("Hello", 3, True),
        ("Hi", 3, False),
        ("", 1, False),
        ("   ", 1, False),
        (None, 1, False),
        ("A" * 300, 300, True),
    ]

    for text, min_len, expected in test_cases:
        result = is_text_usable(text, min_len)
        status = "✓" if result == expected else "✗"
        print(f"{status} is_text_usable({repr(text[:20])}..., {min_len}) = {result} (expected {expected})")


if __name__ == "__main__":
    # Run manual tests
    manual_test_text_usability()
