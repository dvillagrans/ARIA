"""
TDD RED tests for project_resolver.

Tests are written BEFORE implementation. They MUST fail until task 4.2 is done.

Spec §3:
- Fetch active projects for user_id (is_active=True).
- Fuzzy ratio match against project_hint, threshold 0.6.
- Fallback to "Personal" project when no hint or no match above threshold.
- Never raises — always returns a project.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def _make_projects(*names):
    """Helper: list of project dicts with given names."""
    return [{"id": str(uuid4()), "name": n, "is_active": True} for n in names]


# ---------------------------------------------------------------------------
# Test: resolve — no hint → returns Personal project
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_no_hint_returns_personal():
    from app.services.project_resolver import resolve

    projects = _make_projects("Work", "Personal", "Study")
    result = await resolve(None, projects)

    assert result["name"] == "Personal"


# ---------------------------------------------------------------------------
# Test: resolve — exact match
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_exact_match():
    from app.services.project_resolver import resolve

    projects = _make_projects("Work", "Personal", "Study")
    result = await resolve("Work", projects)

    assert result["name"] == "Work"


# ---------------------------------------------------------------------------
# Test: resolve — fuzzy match above threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_fuzzy_match_above_threshold():
    """'wrk' should match 'Work' with score above 0.6."""
    from app.services.project_resolver import resolve

    projects = _make_projects("Work", "Personal")
    result = await resolve("wrk", projects)

    assert result["name"] == "Work"


@pytest.mark.asyncio
async def test_resolve_case_insensitive_match():
    """'work' should match 'Work'."""
    from app.services.project_resolver import resolve

    projects = _make_projects("Work", "Personal")
    result = await resolve("work", projects)

    assert result["name"] == "Work"


# ---------------------------------------------------------------------------
# Test: resolve — no match above threshold → returns Personal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_below_threshold_fallback_to_personal():
    """'xyz123' should not match any project → returns Personal."""
    from app.services.project_resolver import resolve

    projects = _make_projects("Work", "Personal", "Study")
    result = await resolve("xyz123", projects)

    assert result["name"] == "Personal"


# ---------------------------------------------------------------------------
# Test: resolve — empty project list → returns None (edge case, should not
# happen in practice due to Personal project guarantee)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_empty_projects_returns_none():
    """With no projects at all, resolve returns None (no Personal to fall back to)."""
    from app.services.project_resolver import resolve

    result = await resolve(None, [])

    assert result is None


# ---------------------------------------------------------------------------
# Test: resolve — project_hint matches best among multiple projects
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_returns_best_match():
    """Among 'Workout' and 'Work Tasks', 'Work' should match 'Work Tasks' better."""
    from app.services.project_resolver import resolve

    projects = _make_projects("Workout", "Work Tasks", "Personal")
    result = await resolve("work tasks", projects)

    assert result["name"] == "Work Tasks"
