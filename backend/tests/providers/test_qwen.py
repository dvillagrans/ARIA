"""
TDD RED tests for QwenEmbeddingProvider (Phase 1 real implementation).

Tests are written BEFORE implementation. They MUST fail until task 4.6 is done.

Spec §1:
- embed() calls DeepInfra HTTP API via httpx, validates 4096 dims.
- EmbeddingError raised on HTTP 4xx/5xx or dimension mismatch.
- embed_batch() returns vectors in original input order; raises on partial failure.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.providers.base import EmbeddingProvider


def _test_settings():
    from app.core.config import Settings
    return Settings(
        supabase_url="http://localhost:54321",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        deepseek_api_key="test-deepseek-key",
        deepinfra_api_key="test-deepinfra-key",
    )


def _make_httpx_response(status_code: int, json_data: dict):
    """Build a mock httpx Response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        response.raise_for_status.side_effect = HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=response,
        )
    return response


def _make_embed_response(vectors: list[list[float]]) -> dict:
    """Build a DeepInfra-compatible embedding response."""
    return {
        "data": [{"embedding": v, "index": i} for i, v in enumerate(vectors)],
        "model": "Qwen/Qwen3-Embedding",
    }


# ---------------------------------------------------------------------------
# Test: embed — happy path returns 4096 floats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qwen_embed_returns_4096_floats():
    from app.providers.qwen import QwenEmbeddingProvider

    vector = [0.1] * 4096
    response = _make_httpx_response(200, _make_embed_response([vector]))

    with patch("app.providers.qwen.httpx.AsyncClient") as mock_httpx_cls:
        mock_httpx = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_httpx)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.post = AsyncMock(return_value=response)

        provider = QwenEmbeddingProvider(_test_settings())
        result = await provider.embed("Hello world")

    assert isinstance(result, list)
    assert len(result) == 4096
    assert all(isinstance(x, float) for x in result)


# ---------------------------------------------------------------------------
# Test: embed — HTTP 503 → raises EmbeddingError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qwen_embed_raises_on_http_503():
    from app.providers.qwen import QwenEmbeddingProvider, EmbeddingError

    response = _make_httpx_response(503, {})

    with patch("app.providers.qwen.httpx.AsyncClient") as mock_httpx_cls:
        mock_httpx = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_httpx)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.post = AsyncMock(return_value=response)

        provider = QwenEmbeddingProvider(_test_settings())

        with pytest.raises(EmbeddingError) as exc_info:
            await provider.embed("Hello world")

    assert "503" in str(exc_info.value)


@pytest.mark.asyncio
async def test_qwen_embed_raises_on_http_401():
    from app.providers.qwen import QwenEmbeddingProvider, EmbeddingError

    response = _make_httpx_response(401, {"error": "unauthorized"})

    with patch("app.providers.qwen.httpx.AsyncClient") as mock_httpx_cls:
        mock_httpx = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_httpx)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.post = AsyncMock(return_value=response)

        provider = QwenEmbeddingProvider(_test_settings())

        with pytest.raises(EmbeddingError):
            await provider.embed("Hello world")


# ---------------------------------------------------------------------------
# Test: embed — dimension mismatch → raises EmbeddingError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qwen_embed_raises_on_dimension_mismatch():
    from app.providers.qwen import QwenEmbeddingProvider, EmbeddingError

    wrong_vector = [0.1] * 768  # wrong dimension
    response = _make_httpx_response(200, _make_embed_response([wrong_vector]))

    with patch("app.providers.qwen.httpx.AsyncClient") as mock_httpx_cls:
        mock_httpx = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_httpx)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.post = AsyncMock(return_value=response)

        provider = QwenEmbeddingProvider(_test_settings())

        with pytest.raises(EmbeddingError, match="4096"):
            await provider.embed("Hello world")


# ---------------------------------------------------------------------------
# Test: embed_batch — returns vectors in input order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qwen_embed_batch_returns_correct_count():
    from app.providers.qwen import QwenEmbeddingProvider

    texts = ["text1", "text2", "text3", "text4", "text5"]
    vectors = [[float(i)] * 4096 for i in range(5)]
    response = _make_httpx_response(200, _make_embed_response(vectors))

    with patch("app.providers.qwen.httpx.AsyncClient") as mock_httpx_cls:
        mock_httpx = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_httpx)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.post = AsyncMock(return_value=response)

        provider = QwenEmbeddingProvider(_test_settings())
        result = await provider.embed_batch(texts)

    assert len(result) == 5
    for vec in result:
        assert len(vec) == 4096


@pytest.mark.asyncio
async def test_qwen_embed_batch_preserves_order():
    from app.providers.qwen import QwenEmbeddingProvider

    texts = ["a", "b", "c"]
    # Vectors with identifiable first element
    vectors = [[float(i + 1)] * 4096 for i in range(3)]
    response = _make_httpx_response(200, _make_embed_response(vectors))

    with patch("app.providers.qwen.httpx.AsyncClient") as mock_httpx_cls:
        mock_httpx = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_httpx)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.post = AsyncMock(return_value=response)

        provider = QwenEmbeddingProvider(_test_settings())
        result = await provider.embed_batch(texts)

    # First vector starts with 1.0, second with 2.0, etc.
    assert result[0][0] == pytest.approx(1.0)
    assert result[1][0] == pytest.approx(2.0)
    assert result[2][0] == pytest.approx(3.0)
