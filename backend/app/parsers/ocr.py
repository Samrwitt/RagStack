"""Optional OCR for scanned PDFs. Digital text extraction is always tried first."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def ocr_available() -> bool:
    try:
        import pytesseract
        from pdf2image import convert_from_bytes  # noqa: F401

        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


def should_ocr(extracted_chars: int, page_count: int, min_chars_per_page: int | None = None) -> bool:
    settings = get_settings()
    if not settings.pdf_ocr_enabled:
        return False
    threshold = min_chars_per_page if min_chars_per_page is not None else settings.pdf_ocr_min_chars_per_page
    pages = max(page_count, 1)
    return extracted_chars < threshold * pages


def ocr_pdf_pages(data: bytes) -> tuple[list[tuple[int, str]], str | None]:
    """Return (page_number, text) pairs. Warning string if OCR cannot run."""
    if not ocr_available():
        return [], "OCR requested but tesseract/poppler is not available"
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except Exception as exc:
        return [], f"OCR imports failed: {exc}"

    try:
        images = convert_from_bytes(data, dpi=200)
    except Exception as exc:
        logger.warning("parsers.ocr.render_failed", error=str(exc))
        return [], f"PDF rasterization failed: {exc}"

    pages: list[tuple[int, str]] = []
    for index, image in enumerate(images, start=1):
        try:
            text = pytesseract.image_to_string(image) or ""
        except Exception as exc:
            logger.warning("parsers.ocr.page_failed", page=index, error=str(exc))
            text = ""
        pages.append((index, text))
    return pages, None
