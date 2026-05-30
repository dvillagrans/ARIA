"""
Qwen embedding provider — Phase 1 real implementation.

Calls the DeepInfra HTTP API via httpx.AsyncClient with the Qwen3-Embedding
model. Validates the response shape and vector dimensions before returning.

Spec §1 — QwenEmbeddingProvider requirements.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import Settings
from app.core.metrics import aria_embedding_latency_seconds
from app.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)

_OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"
_EMBED_MODEL = "qwen/qwen3-embedding-8b"


class EmbeddingError(Exception):
    """Raised when embedding fails due to API error or dimension mismatch."""


class QwenEmbeddingProvider(EmbeddingProvider):
    """Real embedding provider backed by Qwen3-Embedding via OpenRouter."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.deepinfra_api_key

    async def embed(self, text: str) -> list[float]:
        """
        Embed a single text string and return a 1536-dimensional vector.

        Args:
            text: The text to embed.

        Returns:
            A list of 1536 floats.

        Raises:
            EmbeddingError: On HTTP 4xx/5xx or dimension mismatch.
        """
        results = await self._call_api([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in a single API call, preserving input order.

        Args:
            texts: List of texts to embed.

        Returns:
            List of 1536-float vectors in the same order as input.

        Raises:
            EmbeddingError: If any item fails or dimension mismatches.
        """
        return await self._call_api(texts)

    async def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Shared HTTP call for both embed() and embed_batch()."""
        if aria_embedding_latency_seconds is None:
            return await self._call_api_impl(texts)

        with aria_embedding_latency_seconds.labels(
            model="qwen3-embedding-8b"
        ).time():
            return await self._call_api_impl(texts)

    async def _call_api_impl(self, texts: list[str]) -> list[list[float]]:
        """Internal API call implementation (called with or without timing)."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": _EMBED_MODEL,
            "input": texts,
            "encoding_format": "float",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    _OPENROUTER_EMBED_URL,
                    headers=headers,
                    json=payload,
                )
                if response.status_code >= 400:
                    raise EmbeddingError(
                        f"OpenRouter API returned HTTP {response.status_code}: "
                        f"{response.text[:200]}"
                    )
            except httpx.HTTPStatusError as exc:
                raise EmbeddingError(
                    f"OpenRouter API HTTP error {exc.response.status_code}"
                ) from exc

        data = response.json()

        # Extract vectors sorted by index to preserve input order.
        items = sorted(data["data"], key=lambda x: x["index"])
        vectors: list[list[float]] = [item["embedding"] for item in items]

        # Validate dimensions for all vectors.
        for i, vec in enumerate(vectors):
            if len(vec) != self.EMBEDDING_DIM:
                raise EmbeddingError(
                    f"Expected embedding dimension {self.EMBEDDING_DIM}, "
                    f"got {len(vec)} for item {i}"
                )

        return vectors
