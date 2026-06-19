import logging
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.services.ocr_fallback_service import OCRFallbackService
from app.services.text_extractor import extract_resume_text

logger = logging.getLogger(__name__)


def is_text_usable(text: str | None, min_length: int) -> bool:
    """Check if extracted text meets minimum usability requirements."""
    return text is not None and len(text.strip()) >= min_length


class DocumentTextExtractor:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        logger.debug("Initializing DocumentTextExtractor with OCR enabled=%s, min_length=%d", 
                     self.settings.ocr_fallback_enabled, self.settings.ocr_min_text_length)
        try:
            self.ocr_service = OCRFallbackService(settings=self.settings)
            logger.debug("OCRFallbackService initialized successfully")
        except Exception as exc:
            logger.error("Failed to initialize OCRFallbackService: %s", exc)
            raise

    async def extract_with_fallback(self, content: bytes, extension: str) -> tuple[str, str]:
        """
        Extract text from document with OCR fallback.

        Returns:
            tuple[str, str]: (extracted_text, extraction_method) where extraction_method is
                            either "normal" or "ocr"
        
        Raises:
            HTTPException if extraction fails completely
        """
        # Always attempt normal extraction first
        try:
            extracted_text = await run_in_threadpool(extract_resume_text, content, extension)
            logger.debug("Normal text extraction completed: %d characters", len(extracted_text))
        except Exception as exc:
            logger.warning("Normal text extraction failed: %s. Attempting OCR fallback.", exc)
            if self.settings.ocr_fallback_enabled and extension == ".pdf":
                return await self._try_ocr_fallback(content)
            raise

        # Check if extracted text is usable
        if is_text_usable(extracted_text, self.settings.ocr_min_text_length):
            logger.info("Normal extraction produced sufficient text (%d chars)", len(extracted_text))
            return extracted_text, "normal"

        # Text is insufficient, try OCR if enabled and it's a PDF
        if not self.settings.ocr_fallback_enabled:
            logger.warning(
                "Extracted text is below minimum (%d < %d chars) but OCR fallback is disabled",
                len(extracted_text.strip()),
                self.settings.ocr_min_text_length,
            )
            return extracted_text, "normal"

        if extension != ".pdf":
            logger.warning(
                "Extracted text is below minimum (%d < %d chars) but OCR only supports PDF files (got %s)",
                len(extracted_text.strip()),
                self.settings.ocr_min_text_length,
                extension,
            )
            return extracted_text, "normal"

        logger.info(
            "Normal extraction insufficient (%d < %d chars). Attempting OCR fallback.",
            len(extracted_text.strip()),
            self.settings.ocr_min_text_length,
        )
        return await self._try_ocr_fallback(content)

    async def _try_ocr_fallback(self, content: bytes) -> tuple[str, str]:
        """Execute OCR fallback and return extracted text with method indicator."""
        try:
            ocr_text = await self.ocr_service.extract_text_from_pdf_via_ocr(content)
            if is_text_usable(ocr_text, 40):
                logger.info("OCR fallback succeeded: %d characters extracted", len(ocr_text))
                return ocr_text, "ocr"
            logger.warning("OCR fallback produced insufficient text (%d characters)", len(ocr_text))
            return ocr_text, "ocr"
        except Exception as exc:
            logger.error("OCR fallback failed: %s", exc)
            raise
