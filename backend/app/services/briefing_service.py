"""
Briefing service.

Implements lazy-computed daily briefing with 3-state cache logic:
  State A (fresh): row exists, invalidated_at IS NULL → return cached
  State B (generate): no row OR (invalidated AND age >= DEBOUNCE) → generate + upsert
  State C (stale): row exists, invalidated, age < DEBOUNCE → return stale

ADR-3: _score_task() is a pure function (no DB, unit-testable).
ADR-4: invalidate() is awaited inline in chat.py (not fire-and-forget).
ADR-5: briefing saved as single assistant turn via db.table("conversations").insert()
       — do NOT use conversation_service.save() (it inserts two rows).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import Settings
from app.core.metrics import (
    aria_briefing_cache_hits_total,
    aria_briefing_latency_seconds,
)
from app.providers.base import LLMProvider
from app.schemas.briefing import BriefingResponse

logger = logging.getLogger(__name__)

_BRIEFING_PROMPT = """You are ARIA, a personal AI assistant. Generate a concise, warm daily briefing for the user. Use the context below to highlight the most important task, mention any events today, and note any pending reminders. Keep it to 3-4 sentences. Be practical and encouraging.

Context:
{context}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_or_generate(
    user_id: UUID,
    db,
    llm: LLMProvider,
    settings: Settings,
) -> BriefingResponse:
    """
    Retrieve or generate today's briefing for a user.

    Evaluates 3 cache states and branches accordingly.
    """
    # 1. Fetch user timezone.
    tz_resp = (
        await db.table("users")
        .select("timezone")
        .eq("id", str(user_id))
        .single()
        .execute()
    )
    raw_tz: str = "UTC"
    if tz_resp and tz_resp.data:
        raw_tz = tz_resp.data.get("timezone") or "UTC"

    try:
        user_tz = ZoneInfo(raw_tz)
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning("briefing_service: unknown timezone %r, falling back to UTC", raw_tz)
        user_tz = ZoneInfo("UTC")

    today_local: date = datetime.now(tz=user_tz).date()

    # 2. Fetch existing briefing row for today.
    row_resp = (
        await db.table("briefings")
        .select("content, invalidated_at, date, created_at")
        .eq("user_id", str(user_id))
        .eq("date", today_local.isoformat())
        .execute()
    )
    rows = row_resp.data if row_resp and row_resp.data else []
    row = rows[0] if rows else None

    now_utc = datetime.now(timezone.utc)

    # 3. Evaluate 3-state logic.
    if row:
        raw_inv = row.get("invalidated_at")
        if raw_inv is None:
            # State A: fresh cache hit.
            logger.debug("briefing_service: cache hit (fresh) for user=%s", user_id)
            if aria_briefing_cache_hits_total is not None:
                aria_briefing_cache_hits_total.labels(result="hit").inc()
            raw_created = row.get("created_at") or now_utc.isoformat()
            generated_at = _parse_dt(raw_created)
            return BriefingResponse(
                content=row["content"],
                cached=True,
                stale=False,
                date=today_local,
                generated_at=generated_at,
            )

        # Row is invalidated — check debounce.
        invalidated_at = _parse_dt(raw_inv)
        age_minutes = (now_utc - invalidated_at).total_seconds() / 60

        if age_minutes < settings.BRIEFING_DEBOUNCE_MINUTES:
            # State C: stale serve within debounce window.
            logger.debug(
                "briefing_service: stale serve for user=%s (age=%.1f min < debounce=%d)",
                user_id,
                age_minutes,
                settings.BRIEFING_DEBOUNCE_MINUTES,
            )
            if aria_briefing_cache_hits_total is not None:
                aria_briefing_cache_hits_total.labels(result="hit").inc()
            raw_created = row.get("created_at") or now_utc.isoformat()
            generated_at = _parse_dt(raw_created)
            return BriefingResponse(
                content=row["content"],
                cached=True,
                stale=True,
                date=today_local,
                generated_at=generated_at,
            )

    # State B: generate (row missing or debounce expired).
    logger.info("briefing_service: generating briefing for user=%s date=%s", user_id, today_local)

    if aria_briefing_cache_hits_total is not None:
        aria_briefing_cache_hits_total.labels(result="miss").inc()

    if aria_briefing_latency_seconds is not None:
        with aria_briefing_latency_seconds.time():
            content = await _generate(user_id, today_local, db, llm, settings)
    else:
        content = await _generate(user_id, today_local, db, llm, settings)
    generated_at = datetime.now(timezone.utc)

    return BriefingResponse(
        content=content,
        cached=False,
        stale=False,
        date=today_local,
        generated_at=generated_at,
    )


async def invalidate(user_id: UUID, db) -> None:
    """
    Set invalidated_at = now() on today's briefing row.

    Silent no-op when no row exists for today.
    ADR-4: called synchronously (awaited) in chat.py — not fire-and-forget.
    """
    tz_resp = (
        await db.table("users")
        .select("timezone")
        .eq("id", str(user_id))
        .single()
        .execute()
    )
    raw_tz = "UTC"
    if tz_resp and tz_resp.data:
        raw_tz = tz_resp.data.get("timezone") or "UTC"
    try:
        user_tz = ZoneInfo(raw_tz)
    except (ZoneInfoNotFoundError, KeyError):
        user_tz = ZoneInfo("UTC")
    today_local: date = datetime.now(tz=user_tz).date()

    await (
        db.table("briefings")
        .update({"invalidated_at": datetime.now(timezone.utc).isoformat()})
        .eq("user_id", str(user_id))
        .eq("date", today_local.isoformat())
        .execute()
    )
    logger.debug("briefing_service: invalidated briefing for user=%s date=%s", user_id, today_local)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _generate(
    user_id: UUID,
    today: date,
    db,
    llm: LLMProvider,
    settings: Settings,
) -> str:
    """
    Run 4 parallel queries, score tasks, call LLM, persist result.

    Returns the generated briefing text.
    """
    tomorrow = today + timedelta(days=1)

    # 4 parallel queries.
    tasks_coro = (
        db.table("tasks")
        .select("id, title, status, priority, energy_level, deadline, created_at, project_id")
        .eq("status", "pending")
        .execute()
    )
    events_coro = (
        db.table("events")
        .select("id, title, starts_at, duration_min, type")
        .eq("user_id", str(user_id))
        .execute()
    )
    reminders_coro = (
        db.table("reminders")
        .select("id, title, due_at, is_done")
        .eq("user_id", str(user_id))
        .eq("is_done", False)
        .execute()
    )
    projects_coro = (
        db.table("projects")
        .select("id, name")
        .eq("user_id", str(user_id))
        .eq("is_active", True)
        .execute()
    )

    tasks_resp, events_resp, reminders_resp, projects_resp = await asyncio.gather(
        tasks_coro, events_coro, reminders_coro, projects_coro,
        return_exceptions=True,
    )

    tasks: list[dict] = _safe_data(tasks_resp)
    events: list[dict] = _safe_data(events_resp)
    reminders: list[dict] = _safe_data(reminders_resp)
    projects: list[dict] = _safe_data(projects_resp)

    # Filter events to today only (using starts_at).
    events_today = [
        e for e in events
        if e.get("starts_at") and _parse_dt(e["starts_at"]).date() == today
    ]
    events_today_count = len(events_today)

    # Score and sort tasks.
    scored = sorted(
        tasks,
        key=lambda t: _score_task(t, events_today_count),
        reverse=True,
    )
    top_task = scored[0] if scored else None

    # Filter reminders due today or tomorrow.
    reminders_due = [
        r for r in reminders
        if r.get("due_at") and _parse_dt(r["due_at"]).date() in (today, tomorrow)
    ]

    # Build context string.
    context_parts = []
    if top_task:
        context_parts.append(
            f"Top priority task: '{top_task.get('title', '')}' "
            f"(priority {top_task.get('priority', 3)}, "
            f"deadline: {top_task.get('deadline') or 'none'})"
        )
    if events_today:
        titles = ", ".join(e.get("title", "") for e in events_today[:3])
        context_parts.append(f"Today's events ({events_today_count}): {titles}")
    if reminders_due:
        r_titles = ", ".join(r.get("title", "") for r in reminders_due[:3])
        context_parts.append(f"Pending reminders: {r_titles}")
    if projects:
        p_names = ", ".join(p.get("name", "") for p in projects[:3])
        context_parts.append(f"Active projects: {p_names}")
    context_parts.append(f"Date: {today.isoformat()}")

    briefing_context = "\n".join(context_parts) if context_parts else "No items found for today."
    prompt = _BRIEFING_PROMPT.format(context=briefing_context)

    content = await llm.reason(prompt, context=[briefing_context])

    # UPSERT briefings row (INSERT ... ON CONFLICT DO UPDATE).
    now_iso = datetime.now(timezone.utc).isoformat()
    upsert_payload = {
        "user_id": str(user_id),
        "date": today.isoformat(),
        "content": content,
        "invalidated_at": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    try:
        await (
            db.table("briefings")
            .upsert(upsert_payload, on_conflict="user_id,date")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("briefing_service: upsert failed (non-fatal): %s", exc)

    # Persist single assistant turn to conversations (ADR-5 — direct insert, not conversation_service.save).
    metadata = {
        "intent": "briefing",
        "cached": False,
        "stale": False,
        "date": today.isoformat(),
        "generated_at": now_iso,
    }
    try:
        await (
            db.table("conversations")
            .insert({
                "user_id": str(user_id),
                "role": "assistant",
                "content": content,
                "metadata": metadata,
            })
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("briefing_service: conversation insert failed (non-fatal): %s", exc)

    return content


def _score_task(task: dict, events_today_count: int) -> float:
    """
    Pure deterministic task scoring function.

    Formula:
        total = deadline_score * 3 + priority_score + age_score - energy_penalty

    Deadline buckets:
        10 = today
         7 = tomorrow
         5 = this week (2-6 days out)
         1 = later (>6 days)
         0 = no deadline

    Priority:   (6 - priority) * 2   [priority 1 → 10, priority 5 → 2]
    Age score:  age_days * 0.1
    Penalty:    2 if energy_level=="high" AND events_today_count >= 3 else 0
    """
    today = date.today()

    # Deadline score.
    raw_deadline = task.get("deadline")
    deadline_score: float = 0.0
    if raw_deadline:
        try:
            dl_date = _parse_dt(raw_deadline).date()
            delta = (dl_date - today).days
            if delta <= 0:
                deadline_score = 10.0
            elif delta == 1:
                deadline_score = 7.0
            elif delta <= 6:
                deadline_score = 5.0
            else:
                deadline_score = 1.0
        except (ValueError, TypeError):
            deadline_score = 0.0

    # Priority score.
    priority = int(task.get("priority") or 3)
    priority_score: float = (6 - priority) * 2

    # Age score.
    raw_created = task.get("created_at")
    age_score: float = 0.0
    if raw_created:
        try:
            created_date = _parse_dt(raw_created).date()
            age_days = (today - created_date).days
            age_score = max(age_days, 0) * 0.1
        except (ValueError, TypeError):
            age_score = 0.0

    # Energy penalty.
    energy_penalty: float = 0.0
    if task.get("energy_level") == "high" and events_today_count >= 3:
        energy_penalty = 2.0

    return deadline_score * 3 + priority_score + age_score - energy_penalty


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _parse_dt(raw: str) -> datetime:
    """Parse an ISO datetime string, always returning UTC-aware datetime."""
    # Handle PostgreSQL timestamptz format (space separator, +00 suffix)
    raw = raw.strip()
    # Replace space with T if needed
    if " " in raw and "T" not in raw:
        raw = raw.replace(" ", "T", 1)
    # Normalize +00 → +00:00
    if raw.endswith("+00"):
        raw = raw + ":00"

    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_data(resp) -> list[dict]:
    """Extract .data list from a Supabase response, returning [] on error."""
    if isinstance(resp, Exception):
        logger.warning("briefing_service: query failed: %s", resp)
        return []
    return resp.data if resp and resp.data else []
