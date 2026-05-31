"""
Google Calendar sync service.

Syncs ARIA reminders to Google Calendar so they appear in Notion Calendar.
Uses the existing Google OAuth2 credentials from settings.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Cache the calendar service per-settings to avoid rebuilding on every call.
_calendar_service = None
_calendar_creds: Credentials | None = None


def _get_calendar_creds(settings: Settings) -> Credentials:
    """Build Google OAuth2 credentials from settings."""
    return Credentials(
        token=None,
        refresh_token=settings.calendar_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def _get_calendar_service(settings: Settings):
    """Get or create a Google Calendar API service."""
    global _calendar_service, _calendar_creds
    creds = _get_calendar_creds(settings)
    # Rebuild if creds changed (e.g. different refresh token)
    if _calendar_creds is None or _calendar_creds.refresh_token != creds.refresh_token:
        _calendar_service = build("calendar", "v3", credentials=creds)
        _calendar_creds = creds
    return _calendar_service


def _build_event_body(title: str, due_at_iso: str, reminder_id: str) -> dict:
    """Build a Google Calendar event body from reminder data."""
    due_at = datetime.fromisoformat(due_at_iso.replace("Z", "+00:00"))
    # Default event duration: 15 minutes for reminders
    end_at = due_at + timedelta(minutes=15)

    return {
        "summary": f"⏰ {title}",
        "description": f"ARIA Reminder ID: {reminder_id}",
        "start": {
            "dateTime": due_at.isoformat(),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_at.isoformat(),
            "timeZone": "UTC",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 0},
                {"method": "popup", "minutes": 5},
            ],
        },
    }


async def sync_reminder_to_calendar(
    reminder_id: str,
    title: str,
    due_at_iso: str,
    calendar_event_id: str | None,
    settings: Settings,
) -> str | None:
    """
    Create or update a Google Calendar event for a reminder.

    Returns the Google Calendar event ID, or None if sync failed.
    """
    if not settings.calendar_refresh_token:
        logger.debug("calendar sync: no refresh token configured, skipping")
        return None

    try:
        service = _get_calendar_service(settings)
        event_body = _build_event_body(title, due_at_iso, reminder_id)

        if calendar_event_id:
            # Update existing event
            try:
                result = (
                    service.events()
                    .update(calendarId="primary", eventId=calendar_event_id, body=event_body)
                    .execute()
                )
                logger.info("calendar sync: updated event %s", calendar_event_id)
                return result["id"]
            except Exception as exc:
                logger.warning("calendar sync: update failed, creating new: %s", exc)
                # Fall through to create

        # Create new event
        result = (
            service.events()
            .insert(calendarId="primary", body=event_body)
            .execute()
        )
        logger.info("calendar sync: created event %s", result["id"])
        return result["id"]

    except Exception as exc:
        logger.error("calendar sync: failed: %s", exc)
        return None


async def delete_calendar_event(
    calendar_event_id: str,
    settings: Settings,
) -> bool:
    """Delete a Google Calendar event. Returns True on success."""
    if not settings.calendar_refresh_token or not calendar_event_id:
        return False

    try:
        service = _get_calendar_service(settings)
        service.events().delete(
            calendarId="primary", eventId=calendar_event_id
        ).execute()
        logger.info("calendar sync: deleted event %s", calendar_event_id)
        return True
    except Exception as exc:
        logger.warning("calendar sync: delete failed: %s", exc)
        return False
