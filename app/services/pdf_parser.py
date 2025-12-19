"""PDF text extraction module.

Pure function interface for Temporal Activity compatibility.
No disk I/O - works entirely on bytes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import pdfplumber

logger = logging.getLogger(__name__)


class PDFError(Exception):
    """Base class for PDF-related errors."""

    pass


class PDFValidationError(PDFError):
    """Pre-parse validation failures - final, no retry.

    Raised for: not a PDF, too large, too many pages, encrypted, scanned.
    """

    pass


class PDFParseError(PDFError):
    """Runtime parse failures - may be retried.

    Raised for: corrupted or unparseable PDF content.
    """

    pass


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Immutable result of PDF text extraction."""

    text: str
    page_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


def extract_text_and_pages(
    data: bytes,
    *,
    max_size_mb: int = 25,
    max_pages: int = 100,
) -> ParseResult:
    """Extract text content and page count from PDF bytes.

    Args:
        data: Raw PDF file bytes.
        max_size_mb: Maximum allowed file size in MB.
        max_pages: Maximum allowed page count.

    Returns:
        ParseResult with concatenated text (pages separated by \\n\\n)
        and total page count.

    Raises:
        PDFValidationError: Not a PDF, too large, too many pages, encrypted, or scanned.
        PDFParseError: Corrupted or unparseable PDF.
    """
    # 1. Check PDF header (cheap)
    if not data.startswith(b"%PDF"):
        raise PDFValidationError("unsupported content: missing PDF header")

    # 2. Check file size (cheap)
    max_size_bytes = max_size_mb * 1024 * 1024
    if len(data) > max_size_bytes:
        raise PDFValidationError(
            f"file too large: {len(data) / 1024 / 1024:.1f}MB > {max_size_mb}MB"
        )

    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            # 3. Check page count
            page_count = len(pdf.pages)
            if page_count > max_pages:
                raise PDFValidationError(
                    f"too many pages: {page_count} > {max_pages}"
                )

            # 4. Extract text from all pages
            # Note: Encrypted PDFs will fail at open() or extract_text()
            pages_text: list[str] = []
            has_any_text = False

            for page in pdf.pages:
                page_text = page.extract_text() or ""
                stripped = page_text.strip()
                pages_text.append(stripped)
                if stripped:
                    has_any_text = True

            # 6. Check for scanned/image-only PDF
            if not has_any_text:
                raise PDFValidationError(
                    "no text content: PDF may be scanned/image-only (OCR not supported)"
                )

            full_text = "\n\n".join(pages_text).strip()
            return ParseResult(text=full_text, page_count=page_count)

    except PDFValidationError:
        raise
    except Exception as e:
        logger.warning("PDF parse failed: %s", e, exc_info=True)
        raise PDFParseError(f"failed to parse PDF: {type(e).__name__}") from e


__all__ = [
    "PDFError",
    "PDFValidationError",
    "PDFParseError",
    "ParseResult",
    "extract_text_and_pages",
]
