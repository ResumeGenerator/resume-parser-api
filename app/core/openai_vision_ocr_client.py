import base64
import logging
from io import BytesIO

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

OCR_SYSTEM_PROMPT = """You are an OCR engine specialized in extracting text from resume documents.

Extract all visible text from this resume page image with high accuracy.
- Preserve the original reading order as much as possible.
- Handle multi-column layouts correctly.
- Maintain proper spacing and line breaks.
- Do not summarize or rewrite content.
- Do not invent missing text.
- Ignore decorative elements, borders, icons, and background colors.
- Return only the extracted plain text for this page."""


class OpenAIVisionOCRClient:
    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OCR fallback.")
        self.api_key = settings.openai_api_key
        self.model = settings.ocr_model

    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        """Extract text from a resume page image using OpenAI vision model."""
        try:
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        except Exception as exc:
            logger.error("Failed to base64 encode image: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to process image for OCR.",
            ) from exc

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_SYSTEM_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except Exception as exc:
            logger.error("OpenAI vision API request failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OpenAI vision API request failed.",
            ) from exc

        if response.status_code >= 400:
            logger.error("OpenAI vision API error: %s", response.text)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenAI vision API failed: {response.text}",
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Failed to parse OpenAI vision response: %s", response.text)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to parse OpenAI vision response.",
            ) from exc

        return content if isinstance(content, str) else ""

    @staticmethod
    def convert_pdf_pages_to_images(pdf_content: bytes, dpi: int, max_pages: int | None = None) -> list[bytes]:
        """Convert PDF pages to PNG images using PyMuPDF."""
        try:
            import fitz
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PyMuPDF is required for OCR fallback.",
            )

        images: list[bytes] = []
        try:
            with fitz.open(stream=pdf_content, filetype="pdf") as document:
                total_pages = len(document)
                pages_to_process = min(total_pages, max_pages or total_pages)

                for page_num in range(pages_to_process):
                    page = document[page_num]
                    zoom = dpi / 72.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)

                    img_bytes = BytesIO()
                    img_bytes.write(pix.tobytes(output="png"))
                    images.append(img_bytes.getvalue())
                    logger.debug("Converted PDF page %d to image (DPI: %d)", page_num + 1, dpi)

        except Exception as exc:
            logger.error("Failed to convert PDF to images: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to convert PDF to images for OCR.",
            ) from exc

        return images
