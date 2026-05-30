"""
Provider interfaces — single source of truth for LLM and embedding contracts.

EMBEDDING_DIM is the canonical constant for the vector dimension used across
the entire ARIA codebase. The only other place this value appears is as a
SQL comment in supabase/migrations/0001_init.sql.
"""

from abc import ABC, abstractmethod
from typing import ClassVar


class LLMProvider(ABC):
    """Abstract base class for all language model providers."""

    @abstractmethod
    async def classify(
        self,
        message: str,
        *,
        system: str | None = None,
    ) -> dict:
        """
        Classify or parse a user message into a structured dict.

        Args:
            message: The raw user message to classify.
            system: Optional system prompt override.

        Returns:
            A dict with at minimum an 'intent' key.
        """
        ...

    @abstractmethod
    async def reason(
        self,
        prompt: str,
        *,
        context: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> str:
        """
        Generate a reasoned natural-language response.

        Args:
            prompt: The instruction or question to reason about.
            context: Optional RAG context passages.
            history: Optional conversation history (role/content dicts).

        Returns:
            The model's text response.
        """
        ...


class EmbeddingProvider(ABC):
    """Abstract base class for all embedding providers."""

    EMBEDDING_DIM: ClassVar[int] = 4096
    """
    Canonical embedding dimension for ARIA.
    Must match vector(4096) in supabase/migrations/0001_schema.sql.
    Do NOT repeat this literal elsewhere in Python code.
    """

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """
        Embed a single text string.

        Args:
            text: The text to embed.

        Returns:
            A float list of length EMBEDDING_DIM.
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple text strings in a single API call.

        Args:
            texts: List of texts to embed.

        Returns:
            List of float lists, each of length EMBEDDING_DIM.
        """
        ...
