"""
Tests for provider interface contracts.

Spec requirements:
- LLMProvider and EmbeddingProvider are ABCs — cannot be instantiated directly.
- EmbeddingProvider.EMBEDDING_DIM == 1536 (single source of truth).
- Phase 1: concrete providers call real APIs; stub tests removed.
  Real provider tests live in tests/providers/.
"""

import pytest

from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.qwen import QwenEmbeddingProvider


# ---------------------------------------------------------------------------
# ABC instantiation guard
# ---------------------------------------------------------------------------

def test_llm_provider_is_abstract():
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        LLMProvider()  # type: ignore[abstract]


def test_embedding_provider_is_abstract():
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        EmbeddingProvider()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# EMBEDDING_DIM — single source of truth
# ---------------------------------------------------------------------------

def test_embedding_dim_is_1536():
    assert EmbeddingProvider.EMBEDDING_DIM == 4096


def test_embedding_dim_inherited_by_qwen():
    assert QwenEmbeddingProvider.EMBEDDING_DIM == 4096
