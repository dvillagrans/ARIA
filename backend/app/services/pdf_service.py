"""
PDF service — on-demand PDF text extraction.

Wraps pypdf extraction for PDFs downloaded from URLs or read from local paths.
Follows the same extraction pattern as routes/documents.py _extract_text().

Design: sdd/aria-study-tools/design §Interfaces
"""

from __future__ import annotations

import io
import logging

import httpx

logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT = 30.0  # seconds
_MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB


async def extract_text(file_path: str) -> str:
    """
    Extract text from a PDF file at the given local path.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Concatenated text from all pages.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If no text could be extracted.
    """
    from pypdf import PdfReader  # type: ignore[import-untyped]

    reader = PdfReader(file_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(p for p in pages if p.strip())

    if not text.strip():
        raise ValueError(f"No text extracted from PDF: {file_path}")

    return text


async def download_and_extract(url: str) -> str:
    """
    Download a PDF from a URL and extract its text.

    Args:
        url: HTTP(S) URL pointing to a PDF file.

    Returns:
        Extracted text content from the PDF.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
        httpx.TimeoutException: On download timeout.
        ValueError: If file is too large or no text extracted.
    """
    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    content = response.content
    if len(content) > _MAX_PDF_SIZE:
        raise ValueError(
            f"PDF too large ({len(content)} bytes, max {_MAX_PDF_SIZE})"
        )

    return _extract_from_bytes(content)


def _extract_from_bytes(content: bytes) -> str:
    """
    Extract text from PDF content bytes.

    Mirrors the extraction logic from routes/documents.py _extract_text().

    Args:
        content: Raw PDF file bytes.

    Returns:
        Extracted text from all pages.

    Raises:
        ValueError: If no text could be extracted.
    """
    from pypdf import PdfReader  # type: ignore[import-untyped]

    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(p for p in pages if p.strip())

    if not text.strip():
        raise ValueError("No text extracted from PDF bytes")

    return text
