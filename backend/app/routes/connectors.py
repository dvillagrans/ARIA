"""
Connector sync routes — Phase 4.

POST /connectors/sync/github
POST /connectors/sync/gmail
POST /connectors/sync/calendar

Each route validates the X-API-Key header, calls the corresponding
connector sync function, and returns a SyncResult as JSON.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from supabase._async.client import AsyncClient

from app.core.deps import get_async_supabase, get_embedder, get_llm, get_settings, verify_ingest_key
from app.core.config import Settings
from app.providers.base import EmbeddingProvider, LLMProvider
from app.connectors import github as github_connector
from app.connectors import gmail as gmail_connector
from app.connectors import calendar as calendar_connector
from app.connectors.base import SyncResult

router = APIRouter()


class SyncRequest(BaseModel):
    user_id: UUID


@router.post("/sync/github")
async def sync_github(
    body: SyncRequest,
    _: None = Depends(verify_ingest_key),
    db: AsyncClient = Depends(get_async_supabase),
    llm: LLMProvider = Depends(get_llm),
    embedder: EmbeddingProvider = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Sync GitHub notifications and ingest as tasks/notes."""
    result = await github_connector.sync(db, llm, embedder, settings, user_id=body.user_id)
    return _sync_result_dict(result)


@router.post("/sync/gmail")
async def sync_gmail(
    body: SyncRequest,
    _: None = Depends(verify_ingest_key),
    db: AsyncClient = Depends(get_async_supabase),
    llm: LLMProvider = Depends(get_llm),
    embedder: EmbeddingProvider = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Sync unread Gmail messages and ingest as tasks/notes."""
    result = await gmail_connector.sync(db, llm, embedder, settings, user_id=body.user_id)
    return _sync_result_dict(result)


@router.post("/sync/calendar")
async def sync_calendar(
    body: SyncRequest,
    _: None = Depends(verify_ingest_key),
    db: AsyncClient = Depends(get_async_supabase),
    llm: LLMProvider = Depends(get_llm),
    embedder: EmbeddingProvider = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Sync upcoming Google Calendar events and ingest as events."""
    result = await calendar_connector.sync(db, llm, embedder, settings, user_id=body.user_id)
    return _sync_result_dict(result)


def _sync_result_dict(result: SyncResult) -> dict:
    """Serialize SyncResult to a JSON-compatible dict."""
    return {
        "created": result.created,
        "skipped": result.skipped,
        "failed": result.failed,
        "errors": result.errors,
    }


# Re-export sync functions for test patching convenience
github_sync = github_connector.sync
gmail_sync = gmail_connector.sync
calendar_sync = calendar_connector.sync
