"""
Application configuration loaded from environment variables.

All settings are read at import time via pydantic-settings. Required fields
without defaults raise ValidationError if missing — this is intentional: fail
fast at startup rather than at first use.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # LLM / Embeddings
    deepseek_api_key: str
    deepinfra_api_key: str

    # Runtime
    environment: str = "development"

    # RAG retrieval tuning (ADR-5)
    RAG_MATCH_THRESHOLD: float = 0.5
    RAG_MATCH_COUNT: int = 10

    # Briefing debounce window: serve stale content for this many minutes
    # after invalidation before triggering a full re-generation.
    BRIEFING_DEBOUNCE_MINUTES: int = 30

    # Connector auth — Phase 4
    ingest_api_key: str = ""
    github_token: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    gmail_refresh_token: str = ""
    calendar_refresh_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Safe to call repeatedly."""
    return Settings()
