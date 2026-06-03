"""
Content extraction service — on-demand text extraction from URLs.

Handles PDFs (via pypdf) and HTML pages (via basic text extraction).
Follows the same extraction pattern as routes/documents.py _extract_text().

Design: sdd/aria-study-tools/design §Interfaces
"""

from __future__ import annotations

import io
import logging
import re

import httpx

logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT = 30.0  # seconds
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Common HTML tags to strip
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


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
    Download content from a URL and extract its text.

    Supports PDFs (via pypdf) and HTML/web pages (via tag stripping).
    Detects content type from response headers.

    Args:
        url: HTTP(S) URL pointing to a PDF or HTML page.

    Returns:
        Extracted text content.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
        httpx.TimeoutException: On download timeout.
        ValueError: If file is too large or no text extracted.
    """
    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    content = response.content
    if len(content) > _MAX_FILE_SIZE:
        raise ValueError(
            f"File too large ({len(content)} bytes, max {_MAX_FILE_SIZE})"
        )

    content_type = response.headers.get("content-type", "").lower()

    # Detect if content is PDF
    if b"%PDF" in content[:1024] or "pdf" in content_type:
        return _extract_from_pdf_bytes(content)

    # Otherwise treat as HTML/text
    return _extract_from_html_bytes(content)


def _extract_from_pdf_bytes(content: bytes) -> str:
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


def _extract_from_html_bytes(content: bytes) -> str:
    """
    Extract readable text from HTML content.

    Strips tags, scripts, and styles, then normalizes whitespace.
    Not a full reader-mode parser, but good enough for article content.

    Args:
        content: Raw HTML bytes.

    Returns:
        Extracted text content.

    Raises:
        ValueError: If no text could be extracted.
    """
    try:
        html = content.decode("utf-8", errors="replace")
    except Exception:
        html = content.decode("latin-1", errors="replace")

    # Remove script and style blocks
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    text = _HTML_TAG_RE.sub(" ", html)

    # Decode HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&nbsp;", " ")

    # Normalize whitespace
    text = _WHITESPACE_RE.sub(" ", text).strip()

    if len(text) < 50:
        raise ValueError("No meaningful text extracted from HTML")

    return text
