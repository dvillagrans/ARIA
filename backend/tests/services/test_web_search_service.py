"""
Unit tests for web_search_service.

Tests Tavily API integration and DuckDuckGo fallback.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.core.config import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TAVILY_RESPONSE = {
    "results": [
        {
            "title": "Test Result 1",
            "url": "https://example.com/1",
            "content": "Snippet about AI news",
        },
        {
            "title": "Test Result 2",
            "url": "https://example.com/2",
            "content": "Another snippet about AI",
        },
    ]
}


def _make_settings(tavily_key: str = "") -> Settings:
    """Create a minimal Settings instance for testing."""
    return Settings(
        supabase_url="http://localhost:54321",
        supabase_anon_key="test",
        supabase_service_role_key="test",
        deepseek_api_key="test",
        deepinfra_api_key="test",
        tavily_api_key=tavily_key,
    )


# ---------------------------------------------------------------------------
# Tests: _search_tavily
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_tavily_returns_correct_shape():
    """Tavily search returns list of dicts with title, url, snippet."""
    from app.services.web_search_service import _search_tavily

    mock_response = MagicMock()
    mock_response.json.return_value = TAVILY_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        results = await _search_tavily("AI news", "test-key", 5)

    assert len(results) == 2
    assert results[0]["title"] == "Test Result 1"
    assert results[0]["url"] == "https://example.com/1"
    assert results[0]["snippet"] == "Snippet about AI news"


@pytest.mark.asyncio
async def test_search_tavily_passes_api_key():
    """Tavily search includes the API key in the request payload."""
    from app.services.web_search_service import _search_tavily

    mock_response = MagicMock()
    mock_response.json.return_value = TAVILY_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await _search_tavily("test query", "my-api-key", 3)

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["api_key"] == "my-api-key"
        assert payload["max_results"] == 3


# ---------------------------------------------------------------------------
# Tests: search (top-level function with fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_uses_tavily_when_key_set():
    """search() uses Tavily when tavily_api_key is configured."""
    from app.services.web_search_service import search

    settings = _make_settings(tavily_key="test-key")

    with patch("app.services.web_search_service._search_tavily", new_callable=AsyncMock) as mock_tavily:
        mock_tavily.return_value = [{"title": "t", "url": "u", "snippet": "s"}]
        results = await search("query", settings)

    assert len(results) == 1
    mock_tavily.assert_called_once()


@pytest.mark.asyncio
async def test_search_falls_back_to_ddg_when_no_key():
    """search() uses DuckDuckGo when tavily_api_key is empty."""
    from app.services.web_search_service import search

    settings = _make_settings(tavily_key="")

    with patch("app.services.web_search_service._search_ddg", new_callable=AsyncMock) as mock_ddg:
        mock_ddg.return_value = [{"title": "t", "url": "u", "snippet": "s"}]
        results = await search("query", settings)

    assert len(results) == 1
    mock_ddg.assert_called_once()


@pytest.mark.asyncio
async def test_search_falls_back_to_ddg_on_tavily_failure():
    """search() falls back to DuckDuckGo when Tavily raises an exception."""
    from app.services.web_search_service import search

    settings = _make_settings(tavily_key="test-key")

    with patch("app.services.web_search_service._search_tavily", new_callable=AsyncMock) as mock_tavily, \
         patch("app.services.web_search_service._search_ddg", new_callable=AsyncMock) as mock_ddg:
        mock_tavily.side_effect = httpx.HTTPStatusError("error", request=MagicMock(), response=MagicMock())
        mock_ddg.return_value = [{"title": "fallback", "url": "u", "snippet": "s"}]
        results = await search("query", settings)

    assert len(results) == 1
    assert results[0]["title"] == "fallback"
    mock_ddg.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: _search_ddg (import guard)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_ddg_returns_empty_when_library_missing():
    """_search_ddg returns empty list when duckduckgo_search is not installed."""
    from app.services.web_search_service import _search_ddg

    with patch.dict("sys.modules", {"duckduckgo_search": None}):
        results = await _search_ddg("query", 5)

    assert results == []
