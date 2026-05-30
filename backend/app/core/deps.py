"""
FastAPI dependency injection providers.

All providers are designed to be used with `fastapi.Depends`. Settings is
cached via lru_cache; Supabase clients are created per-request (ADR-01).
"""

from fastapi import Depends, Header, HTTPException
from supabase._async.client import AsyncClient

from app.core.config import Settings, get_settings
from app.core.supabase_client import get_anon_client, get_supabase_client
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.deepseek import DeepSeekProvider
from app.providers.qwen import QwenEmbeddingProvider


def get_llm(settings: Settings = Depends(get_settings)) -> LLMProvider:
    """Return the active LLM provider (DeepSeek)."""
    return DeepSeekProvider(settings)


def get_embedder(settings: Settings = Depends(get_settings)) -> EmbeddingProvider:
    """Return the active embedding provider (Qwen via DeepInfra)."""
    return QwenEmbeddingProvider(settings)


async def get_async_supabase(
    settings: Settings = Depends(get_settings),
) -> AsyncClient:
    """Return a service-role async Supabase client."""
    return await get_supabase_client(settings)


async def get_anon_supabase(
    settings: Settings = Depends(get_settings),
) -> AsyncClient:
    """Return an anon-key async Supabase client (Phase 2+)."""
    return await get_anon_client(settings)


# Alias kept for backward compatibility with any existing call sites.
get_supabase = get_async_supabase


async def verify_ingest_key(
    x_api_key: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    """Validate the X-API-Key header against settings.ingest_api_key.

    Raises HTTP 401 when the key is absent or does not match.
    """
    if not settings.ingest_api_key or x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
