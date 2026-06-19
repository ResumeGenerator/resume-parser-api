import logging
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.openai_vision_ocr_client import OpenAIVisionOCRClient
from app.utils.text_cleaner import clean_resume_text

logger = logging.getLogger(__name__)


class OCRFallbackService:
    def __init__(self, ocr_client: OpenAIVisionOCRClient | None = None, settings: Settings | None = None):
        self.ocr_client = ocr_client or OpenAIVisionOCRClient()
        self.settings = settings or get_settings()

    async def extract_text_from_pdf_via_ocr(self, pdf_content: bytes) -> str:
        """Extract text from PDF using OCR (vision model on page images)."""
        logger.info("Starting OCR fallback for PDF document")

        images = await run_in_threadpool(
            self.ocr_client.convert_pdf_pages_to_images,
            pdf_content,
            self.settings.ocr_dpi,
            self.settings.ocr_max_pages,
        )

        if not images:
            logger.warning("No pages were converted from PDF")
            return ""

        logger.debug("Converted %d PDF pages to images for OCR", len(images))

        page_texts = []
        for page_num, image_bytes in enumerate(images, start=1):
            try:
                text = await self.ocr_client.extract_text_from_image(image_bytes)
                cleaned_text = clean_resume_text(text)
                if cleaned_text:
                    page_texts.append(cleaned_text)
                    logger.debug("OCR extracted %d characters from page %d", len(cleaned_text), page_num)
                else:
                    logger.debug("Page %d contained no extractable text", page_num)
            except Exception as exc:
                logger.error("OCR failed for page %d: %s", page_num, exc)
                raise

        merged_text = "\n\n".join(page_texts)
        logger.info("OCR extraction completed: %d total characters from %d pages", len(merged_text), len(images))
        return merged_text
