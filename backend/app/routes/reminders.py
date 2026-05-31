"""
Reminders CRUD + Google Calendar sync.

GET /reminders/due — overdue reminders
POST /reminders/{id}/acknowledge — mark done + delete calendar event
PATCH /reminders/{id}/update — update reminder + sync calendar
DELETE /reminders/{id} — delete reminder + delete calendar event
POST /reminders/sync-all — bulk sync all pending reminders to calendar
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.deps import get_async_supabase
from app.services.calendar_sync import delete_calendar_event, sync_reminder_to_calendar

logger = logging.getLogger(__name__)

router = APIRouter()


class DueReminder(BaseModel):
    id: str
    title: str
    due_at: str
    amount: float | None = None
    currency: str | None = None
    project_id: str | None = None
    calendar_event_id: str | None = None


class ReminderUpdate(BaseModel):
    title: str | None = None
    due_at: str | None = None
    amount: float | None = None
    currency: str | None = None


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
            .select("id, title, due_at, amount, currency, project_id, calendar_event_id")
            .eq("user_id", user_id)
            .eq("is_done", False)
            .lte("due_at", now)
            .order("due_at", desc=False)
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
            calendar_event_id=r.get("calendar_event_id"),
        )
        for r in (resp.data or [])
    ]


@router.post("/reminders/{reminder_id}/acknowledge")
async def acknowledge_reminder(
    reminder_id: str,
    user_id: str,
    db=Depends(get_async_supabase),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Mark a reminder as done and delete its Google Calendar event."""
    # Fetch the reminder to get calendar_event_id
    try:
        fetch = await (
            db.table("reminders")
            .select("calendar_event_id")
            .eq("id", reminder_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Reminder not found")

    cal_event_id = fetch.data.get("calendar_event_id") if fetch.data else None

    # Mark as done
    try:
        await (
            db.table("reminders")
            .update({"is_done": True})
            .eq("id", reminder_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("reminders/acknowledge: update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    # Delete calendar event
    if cal_event_id:
        await delete_calendar_event(cal_event_id, settings)

    return {"status": "acknowledged", "id": reminder_id}


@router.patch("/reminders/{reminder_id}")
async def update_reminder(
    reminder_id: str,
    body: ReminderUpdate,
    user_id: str,
    db=Depends(get_async_supabase),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Update a reminder and sync changes to Google Calendar."""
    updates = {}
    if body.title is not None:
        updates["title"] = body.title
    if body.due_at is not None:
        updates["due_at"] = body.due_at
    if body.amount is not None:
        updates["amount"] = body.amount
    if body.currency is not None:
        updates["currency"] = body.currency

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        resp = await (
            db.table("reminders")
            .update(updates)
            .eq("id", reminder_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("reminders/update: failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    if not resp.data:
        raise HTTPException(status_code=404, detail="Reminder not found")

    # Sync to Google Calendar
    reminder = resp.data[0] if resp.data else {}
    cal_event_id = reminder.get("calendar_event_id")
    title = updates.get("title", reminder.get("title", ""))
    due_at = updates.get("due_at", reminder.get("due_at", ""))

    new_cal_id = await sync_reminder_to_calendar(
        reminder_id=reminder_id,
        title=title,
        due_at_iso=due_at,
        calendar_event_id=cal_event_id,
        settings=settings,
    )
    if new_cal_id and new_cal_id != cal_event_id:
        try:
            await (
                db.table("reminders")
                .update({"calendar_event_id": new_cal_id})
                .eq("id", reminder_id)
                .execute()
            )
        except Exception as exc:
            logger.warning("reminders/update: failed to save calendar_event_id: %s", exc)

    return {"status": "updated", "id": reminder_id, "calendar_synced": new_cal_id is not None}


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: str,
    user_id: str,
    db=Depends(get_async_supabase),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Delete a reminder and its Google Calendar event."""
    # Fetch calendar_event_id before deleting
    try:
        fetch = await (
            db.table("reminders")
            .select("calendar_event_id")
            .eq("id", reminder_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Reminder not found")

    cal_event_id = fetch.data.get("calendar_event_id") if fetch.data else None

    try:
        await (
            db.table("reminders")
            .delete()
            .eq("id", reminder_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("reminders/delete: failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    # Delete calendar event
    if cal_event_id:
        await delete_calendar_event(cal_event_id, settings)

    return {"status": "deleted", "id": reminder_id}


@router.post("/reminders/sync-all")
async def sync_all_reminders(
    user_id: str,
    db=Depends(get_async_supabase),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Bulk sync all pending (not done) reminders to Google Calendar."""
    try:
        resp = await (
            db.table("reminders")
            .select("id, title, due_at, calendar_event_id")
            .eq("user_id", user_id)
            .eq("is_done", False)
            .execute()
        )
    except Exception as exc:
        logger.error("reminders/sync-all: query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    synced = 0
    for r in (resp.data or []):
        cal_id = await sync_reminder_to_calendar(
            reminder_id=r["id"],
            title=r["title"],
            due_at_iso=str(r["due_at"]),
            calendar_event_id=r.get("calendar_event_id"),
            settings=settings,
        )
        if cal_id and cal_id != r.get("calendar_event_id"):
            try:
                await (
                    db.table("reminders")
                    .update({"calendar_event_id": cal_id})
                    .eq("id", r["id"])
                    .execute()
                )
            except Exception:
                pass
            synced += 1

    return {"synced": synced, "total": len(resp.data or [])}
