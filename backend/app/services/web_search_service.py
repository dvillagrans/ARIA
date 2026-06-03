"""
Web search service — external knowledge retrieval.

Provides web search via Tavily API (primary) with DuckDuckGo fallback
when the Tavily API key is not configured.

Design: sdd/aria-study-tools/design §Interfaces
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

_TAVILY_ENDPOINT = "https://api.tavily.com/search"
_TAVILY_TIMEOUT = 10.0  # seconds
_DDG_TIMEOUT = 10.0


async def search(
    query: str,
    settings: Settings,
    max_results: int = 5,
) -> list[dict]:
    """
    Search the web for the given query.

    Uses Tavily API if tavily_api_key is configured; falls back to
    DuckDuckGo otherwise.

    Args:
        query: The search query string.
        settings: Application settings (provides tavily_api_key).
        max_results: Maximum number of results to return.

    Returns:
        List of dicts with keys: title, url, snippet.
    """
    if settings.tavily_api_key:
        try:
            return await _search_tavily(query, settings.tavily_api_key, max_results)
        except Exception as exc:
            logger.warning("web_search: Tavily failed, falling back to DDG: %s", exc)

    return await _search_ddg(query, max_results)


async def _search_tavily(
    query: str,
    api_key: str,
    max_results: int,
) -> list[dict]:
    """
    Search via Tavily API.

    Args:
        query: Search query.
        api_key: Tavily API key.
        max_results: Max results to return.

    Returns:
        List of dicts with title, url, snippet keys.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
        httpx.TimeoutException: On request timeout.
    """
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "include_answer": False,
    }

    async with httpx.AsyncClient(timeout=_TAVILY_TIMEOUT) as client:
        response = await client.post(_TAVILY_ENDPOINT, json=payload)
        response.raise_for_status()

    data = response.json()
    results: list[dict] = []

    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
        })

    logger.info("web_search: Tavily returned %d results for '%s'", len(results), query)
    return results


async def _search_ddg(
    query: str,
    max_results: int,
) -> list[dict]:
    """
    Search via DuckDuckGo (fallback when Tavily key is missing).

    Uses the duckduckgo_search library if available; otherwise returns
    an empty list with a warning.

    Args:
        query: Search query.
        max_results: Max results to return.

    Returns:
        List of dicts with title, url, snippet keys.
    """
    try:
        from duckduckgo_search import DDGS  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("web_search: duckduckgo_search not installed, returning empty")
        return []

    try:
        ddgs = DDGS()
        raw_results = ddgs.text(query, max_results=max_results)
        results: list[dict] = []
        for item in raw_results:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", ""),
            })
        logger.info("web_search: DDG returned %d results for '%s'", len(results), query)
        return results
    except Exception as exc:
        logger.warning("web_search: DDG search failed: %s", exc)
        return []
