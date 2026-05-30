"""
GET /briefing — daily briefing endpoint.

Returns the 3-state cache result for today's briefing.
Saves a single assistant conversation turn on generation (ADR-5).

Query params:
    user_id: UUID — the authenticated user's ID (injected server-side by Next.js)
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.core.deps import get_async_supabase, get_llm
from app.providers.base import LLMProvider
from app.schemas.briefing import BriefingResponse
from app.services import briefing_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/briefing", response_model=BriefingResponse)
async def get_briefing(
    user_id: UUID = Query(..., description="Authenticated user UUID"),
    llm: LLMProvider = Depends(get_llm),
    db=Depends(get_async_supabase),
    settings: Settings = Depends(get_settings),
) -> BriefingResponse:
    """
    Retrieve or generate today's daily briefing for the user.

    Three cache states:
      - fresh (cached=True, stale=False): row exists, not invalidated
      - stale (cached=True, stale=True): invalidated within debounce window
      - generated (cached=False, stale=False): no row or debounce expired
    """
    try:
        return await briefing_service.get_or_generate(user_id, db, llm, settings)
    except Exception as exc:  # noqa: BLE001
        logger.error("briefing: get_or_generate failed for user=%s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
