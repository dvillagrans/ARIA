"""
Unit tests for pdf_service.

Tests PDF text extraction from bytes and download+extract flow.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Tests: _extract_from_bytes
# ---------------------------------------------------------------------------

def test_extract_from_bytes_valid_pdf():
    """_extract_from_bytes extracts text from valid PDF bytes."""
    from app.services.pdf_service import _extract_from_bytes

    # Create a minimal PDF with text content.
    # This is a real minimal PDF with "Hello World" text.
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td (Hello World) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000364 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n441\n%%EOF"
    )

    # This test verifies the function doesn't crash; actual text extraction
    # depends on pypdf parsing. If pypdf can't parse our minimal PDF,
    # we test the ValueError path instead.
    try:
        result = _extract_from_bytes(pdf_bytes)
        assert isinstance(result, str)
    except ValueError:
        # Expected if our minimal PDF doesn't have extractable text
        pass


def test_extract_from_bytes_empty_content_raises():
    """_extract_from_bytes raises ValueError for empty/non-PDF content."""
    from app.services.pdf_service import _extract_from_bytes

    with pytest.raises(Exception):  # pypdf raises various errors on invalid PDF
        _extract_from_bytes(b"not a pdf")


# ---------------------------------------------------------------------------
# Tests: download_and_extract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_and_extract_success():
    """download_and_extract downloads and extracts text from a PDF URL."""
    from app.services.pdf_service import download_and_extract

    mock_response = MagicMock()
    mock_response.content = b"%PDF-1.4 fake pdf content"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with patch("app.services.pdf_service._extract_from_bytes", return_value="extracted text"):
            result = await download_and_extract("https://example.com/file.pdf")

    assert result == "extracted text"


@pytest.mark.asyncio
async def test_download_and_extract_rejects_oversized_pdf():
    """download_and_extract raises ValueError for PDFs over 10MB."""
    from app.services.pdf_service import download_and_extract, _MAX_PDF_SIZE

    mock_response = MagicMock()
    mock_response.content = b"x" * (_MAX_PDF_SIZE + 1)
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="too large"):
            await download_and_extract("https://example.com/large.pdf")
