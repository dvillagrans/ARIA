"""
Google Calendar → ARIA sync endpoint.

POST /events/sync — import events from Google Calendar to ARIA.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.deps import get_async_supabase
from app.services.calendar_import import sync_calendar_events

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/events/sync")
async def sync_events(
    user_id: str,
    db=Depends(get_async_supabase),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Import events from Google Calendar to ARIA."""
    result = await sync_calendar_events(user_id, settings, db)

    if result.get("error") == "no_token":
        raise HTTPException(
            status_code=400,
            detail="Google Calendar not connected. Run OAuth bootstrap first.",
        )

    return result
