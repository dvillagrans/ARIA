"""
GET /reminders/due — returns overdue reminders that haven't been acknowledged.

Returns reminders where due_at <= now AND is_done = false.
Used by the frontend polling hook to show reminder notifications.

POST /reminders/{id}/acknowledge — marks a reminder as done.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_async_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


class DueReminder(BaseModel):
    id: str
    title: str
    due_at: str
    amount: float | None = None
    currency: str | None = None
    project_id: str | None = None


@router.get("/reminders/due", response_model=list[DueReminder])
async def get_due_reminders(
    user_id: str,
    db=Depends(get_async_supabase),
) -> list[DueReminder]:
    """Return reminders where due_at <= now and is_done = false."""
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        resp = await (
            db.table("reminders")
            .select("id, title, due_at, amount, currency, project_id")
            .eq("user_id", user_id)
            .eq("is_done", False)
            .lte("due_at", now)
            .order("due_at", ascending=True)
            .limit(20)
            .execute()
        )
    except Exception as exc:
        logger.error("reminders/due: query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    return [
        DueReminder(
            id=str(r["id"]),
            title=r["title"],
            due_at=str(r["due_at"]),
            amount=r.get("amount"),
            currency=r.get("currency"),
            project_id=str(r["project_id"]) if r.get("project_id") else None,
        )
        for r in (resp.data or [])
    ]


@router.post("/reminders/{reminder_id}/acknowledge")
async def acknowledge_reminder(
    reminder_id: str,
    user_id: str,
    db=Depends(get_async_supabase),
) -> dict:
    """Mark a reminder as done (is_done = true)."""
    try:
        resp = await (
            db.table("reminders")
            .update({"is_done": True})
            .eq("id", reminder_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("reminders/acknowledge: update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    if not resp.data:
        raise HTTPException(status_code=404, detail="Reminder not found")

    return {"status": "acknowledged", "id": reminder_id}
