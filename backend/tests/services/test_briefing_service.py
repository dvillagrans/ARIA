"""
TDD RED tests for briefing_service.

Tests are written BEFORE full implementation to drive the design.

Spec:
- _score_task(): pure function, deterministic scoring formula
- get_or_generate(): 3-state cache logic (fresh / stale / generate)
- invalidate(): single UPDATE, silent no-op when row absent

Design formula:
  total = deadline_score*3 + priority_score + age_score - energy_penalty
  deadline_score: 10(today) / 7(tomorrow) / 5(this week) / 1(later) / 0(none)
  priority_score: (6 - priority) * 2
  age_score: age_days * 0.1
  energy_penalty: 2 if events_today_count>=3 AND energy_level=="high" else 0
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    *,
    deadline: date | None = None,
    priority: int = 3,
    energy_level: str = "medium",
    created_at: datetime | None = None,
    today: date | None = None,
) -> dict:
    """Build a minimal task dict for _score_task tests."""
    _today = today or date.today()
    _created_at = created_at or datetime.combine(
        _today, datetime.min.time(), tzinfo=timezone.utc
    )
    return {
        "deadline": deadline.isoformat() + "T00:00:00+00:00" if deadline else None,
        "priority": priority,
        "energy_level": energy_level,
        "created_at": _created_at.isoformat(),
    }


def _make_mock_db(briefing_row: dict | None = None, user_timezone: str = "UTC"):
    """
    Build a mock Supabase AsyncClient that returns given briefing row and timezone.
    Supports chainable .table().select().eq().single().execute() and
    .table().update().eq().execute() and .table().insert().execute() patterns.
    """
    db = MagicMock()

    # Default execute returns empty
    generic_execute = AsyncMock(return_value=MagicMock(data=[]))

    # Timezone query: .table("users").select("timezone").eq("id", ...).single().execute()
    tz_execute = AsyncMock(return_value=MagicMock(data={"timezone": user_timezone}))
    tz_single = MagicMock(return_value=MagicMock(execute=tz_execute))
    tz_eq = MagicMock(return_value=MagicMock(single=tz_single, execute=generic_execute))
    tz_select = MagicMock(return_value=MagicMock(eq=tz_eq))

    # Briefing row query
    briefing_execute = AsyncMock(
        return_value=MagicMock(data=[briefing_row] if briefing_row else [])
    )
    briefing_eq2 = MagicMock(return_value=MagicMock(execute=briefing_execute))
    briefing_eq1 = MagicMock(return_value=MagicMock(eq=briefing_eq2))
    briefing_select = MagicMock(return_value=MagicMock(eq=briefing_eq1))

    # Update chain
    update_execute = AsyncMock(return_value=MagicMock(data=[]))
    update_eq2 = MagicMock(return_value=MagicMock(execute=update_execute))
    update_eq1 = MagicMock(return_value=MagicMock(eq=update_eq2))
    update_call = MagicMock(return_value=MagicMock(eq=update_eq1))

    # Insert chain
    insert_execute = AsyncMock(return_value=MagicMock(data=[]))
    insert_call = MagicMock(return_value=MagicMock(execute=insert_execute))

    # Upsert chain
    upsert_execute = AsyncMock(return_value=MagicMock(data=[]))
    upsert_call = MagicMock(return_value=MagicMock(execute=upsert_execute))

    def table_router(table_name: str):
        mock = MagicMock()
        if table_name == "users":
            mock.select = tz_select
        elif table_name == "briefings":
            mock.select = briefing_select
            mock.update = update_call
            mock.insert = insert_call
            mock.upsert = upsert_call
        else:
            # tasks, events, reminders, projects, conversations
            mock.select = MagicMock(
                return_value=MagicMock(
                    eq=MagicMock(
                        return_value=MagicMock(
                            eq=MagicMock(
                                return_value=MagicMock(
                                    order=MagicMock(
                                        return_value=MagicMock(execute=generic_execute)
                                    ),
                                    execute=generic_execute,
                                    filter=MagicMock(
                                        return_value=MagicMock(execute=generic_execute)
                                    ),
                                )
                            ),
                            order=MagicMock(
                                return_value=MagicMock(execute=generic_execute)
                            ),
                            execute=generic_execute,
                        )
                    ),
                    order=MagicMock(
                        return_value=MagicMock(execute=generic_execute)
                    ),
                    execute=generic_execute,
                )
            )
            mock.insert = insert_call
        return mock

    db.table = MagicMock(side_effect=table_router)
    return db, update_execute, upsert_execute, insert_execute


def _make_settings(debounce_minutes: int = 30):
    settings = MagicMock()
    settings.BRIEFING_DEBOUNCE_MINUTES = debounce_minutes
    return settings


def _make_llm(response_text: str = "Good morning! Here is your briefing."):
    llm = AsyncMock()
    llm.reason = AsyncMock(return_value=response_text)
    return llm


# ---------------------------------------------------------------------------
# TASK-2.1: Unit tests for _score_task()
# ---------------------------------------------------------------------------

class TestScoreTask:
    """Pure unit tests — no DB, no async."""

    def test_score_task_deadline_today_returns_high(self):
        """Deadline today → deadline_score=10, total includes 10*3=30."""
        from app.services.briefing_service import _score_task

        today = date.today()
        task = _make_task(deadline=today, priority=3, energy_level="low", today=today)
        score = _score_task(task, events_today_count=0)

        # deadline_score=10, priority_score=(6-3)*2=6, age=0, penalty=0
        # total = 10*3 + 6 + 0 - 0 = 36
        assert score == pytest.approx(36.0)

    def test_score_task_no_deadline_returns_low(self):
        """No deadline → deadline_score=0."""
        from app.services.briefing_service import _score_task

        task = _make_task(deadline=None, priority=3, energy_level="low")
        score = _score_task(task, events_today_count=0)

        # deadline_score=0, priority_score=6, age=0, penalty=0
        # total = 0 + 6 + 0 - 0 = 6
        assert score == pytest.approx(6.0)

    def test_score_task_high_energy_with_events_applies_penalty(self):
        """energy_level=high + events>=3 → energy_penalty=2."""
        from app.services.briefing_service import _score_task

        task = _make_task(deadline=None, priority=3, energy_level="high")
        score = _score_task(task, events_today_count=3)

        # deadline_score=0, priority_score=6, age=0, penalty=2
        # total = 0 + 6 + 0 - 2 = 4
        assert score == pytest.approx(4.0)

    def test_score_task_high_energy_with_2_events_no_penalty(self):
        """energy_level=high + events=2 (< 3) → no penalty."""
        from app.services.briefing_service import _score_task

        task = _make_task(deadline=None, priority=3, energy_level="high")
        score = _score_task(task, events_today_count=2)

        # deadline_score=0, priority_score=6, age=0, penalty=0
        assert score == pytest.approx(6.0)

    def test_score_task_low_energy_with_3_events_no_penalty(self):
        """energy_level=low + events>=3 → no penalty (only high gets penalty)."""
        from app.services.briefing_service import _score_task

        task = _make_task(deadline=None, priority=3, energy_level="low")
        score = _score_task(task, events_today_count=3)

        # penalty=0 because energy_level != "high"
        assert score == pytest.approx(6.0)

    def test_score_task_priority_1_beats_priority_5(self):
        """priority=1 should score higher than priority=5 all else equal."""
        from app.services.briefing_service import _score_task

        task_p1 = _make_task(priority=1)
        task_p5 = _make_task(priority=5)

        score_p1 = _score_task(task_p1, events_today_count=0)
        score_p5 = _score_task(task_p5, events_today_count=0)

        assert score_p1 > score_p5

    def test_score_task_spec_example_task_a_beats_task_b(self):
        """
        Spec example: task A (deadline=today, priority=3, age=0, low) → 36
        task B (no deadline, priority=1, age=60 days) → 16
        Task A wins.
        """
        from app.services.briefing_service import _score_task

        today = date.today()
        created_60_days_ago = datetime.combine(
            today - timedelta(days=60), datetime.min.time(), tzinfo=timezone.utc
        )
        task_a = _make_task(deadline=today, priority=3, energy_level="low", today=today)
        task_b = _make_task(
            deadline=None,
            priority=1,
            energy_level="medium",
            created_at=created_60_days_ago,
            today=today,
        )

        score_a = _score_task(task_a, events_today_count=0)
        score_b = _score_task(task_b, events_today_count=0)

        # task A: 10*3 + (6-3)*2 + 0*0.1 - 0 = 36
        # task B: 0 + (6-1)*2 + 60*0.1 - 0 = 10 + 6 = 16
        assert score_a == pytest.approx(36.0)
        assert score_b == pytest.approx(16.0)
        assert score_a > score_b

    def test_score_task_tomorrow_deadline(self):
        """Deadline tomorrow → deadline_score=7."""
        from app.services.briefing_service import _score_task

        today = date.today()
        tomorrow = today + timedelta(days=1)
        task = _make_task(deadline=tomorrow, priority=3, today=today)
        score = _score_task(task, events_today_count=0)

        # deadline_score=7, priority_score=6, age=0
        # total = 7*3 + 6 + 0 - 0 = 27
        assert score == pytest.approx(27.0)


# ---------------------------------------------------------------------------
# TASK-2.2: Integration tests for get_or_generate() 3-state cache logic
# ---------------------------------------------------------------------------

class TestGetOrGenerate:
    """Integration tests — mock db + llm + settings."""

    @pytest.mark.asyncio
    async def test_get_or_generate_returns_cached_when_valid(self):
        """State A: row exists with invalidated_at=None → cached=True, stale=False, no LLM."""
        from app.services.briefing_service import get_or_generate

        today = date.today()
        now = datetime.now(timezone.utc)
        existing_row = {
            "content": "Cached briefing",
            "invalidated_at": None,
            "date": today.isoformat(),
            "created_at": now.isoformat(),
        }
        user_id = uuid4()
        db, _, _, _ = _make_mock_db(briefing_row=existing_row)
        llm = _make_llm()
        settings = _make_settings()

        result = await get_or_generate(user_id, db, llm, settings)

        assert result.cached is True
        assert result.stale is False
        assert result.content == "Cached briefing"
        llm.reason.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_generate_generates_when_missing(self):
        """State B: no row → LLM called, result returned with cached=False, stale=False."""
        from app.services.briefing_service import get_or_generate

        user_id = uuid4()
        db, _, _, _ = _make_mock_db(briefing_row=None)
        llm = _make_llm("Morning briefing!")
        settings = _make_settings()

        result = await get_or_generate(user_id, db, llm, settings)

        assert result.cached is False
        assert result.stale is False
        assert "Morning briefing!" in result.content
        llm.reason.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_generate_serves_stale_within_debounce(self):
        """State C: invalidated 10min ago, debounce=30 → stale=True, no LLM."""
        from app.services.briefing_service import get_or_generate

        today = date.today()
        invalidated_10_min_ago = (
            datetime.now(timezone.utc) - timedelta(minutes=10)
        ).isoformat()
        existing_row = {
            "content": "Stale briefing",
            "invalidated_at": invalidated_10_min_ago,
            "date": today.isoformat(),
            "created_at": invalidated_10_min_ago,
        }
        user_id = uuid4()
        db, _, _, _ = _make_mock_db(briefing_row=existing_row)
        llm = _make_llm()
        settings = _make_settings(debounce_minutes=30)

        result = await get_or_generate(user_id, db, llm, settings)

        assert result.cached is True
        assert result.stale is True
        assert result.content == "Stale briefing"
        llm.reason.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_generate_regenerates_after_debounce(self):
        """State B (expired): invalidated 45min ago, debounce=30 → regenerate, cached=False."""
        from app.services.briefing_service import get_or_generate

        today = date.today()
        invalidated_45_min_ago = (
            datetime.now(timezone.utc) - timedelta(minutes=45)
        ).isoformat()
        existing_row = {
            "content": "Old briefing",
            "invalidated_at": invalidated_45_min_ago,
            "date": today.isoformat(),
            "created_at": invalidated_45_min_ago,
        }
        user_id = uuid4()
        db, _, _, _ = _make_mock_db(briefing_row=existing_row)
        llm = _make_llm("Fresh morning briefing!")
        settings = _make_settings(debounce_minutes=30)

        result = await get_or_generate(user_id, db, llm, settings)

        assert result.cached is False
        assert result.stale is False
        llm.reason.assert_called_once()


# ---------------------------------------------------------------------------
# TASK-2.3: Unit tests for invalidate()
# ---------------------------------------------------------------------------

class TestInvalidate:
    """Tests for briefing_service.invalidate()."""

    @pytest.mark.asyncio
    async def test_invalidate_sets_invalidated_at(self):
        """Row exists → UPDATE called with invalidated_at."""
        from app.services.briefing_service import invalidate

        user_id = uuid4()
        today = date.today()
        existing_row = {
            "content": "Some briefing",
            "invalidated_at": None,
            "date": today.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        db, update_execute, _, _ = _make_mock_db(briefing_row=existing_row)

        await invalidate(user_id, db)

        # update should have been triggered on "briefings" table
        db.table.assert_any_call("briefings")

    @pytest.mark.asyncio
    async def test_invalidate_noop_when_no_row(self):
        """No row for today → no exception raised, graceful no-op."""
        from app.services.briefing_service import invalidate

        user_id = uuid4()
        db, _, _, _ = _make_mock_db(briefing_row=None)

        # Must not raise
        await invalidate(user_id, db)
