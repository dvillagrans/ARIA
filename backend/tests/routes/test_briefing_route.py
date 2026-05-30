"""
TDD RED tests for GET /briefing route.

Tests are written before the route exists. They will fail (RED) until
TASK-3.3 creates the route and TASK-3.4 registers it in main.py.

Spec: New Capability — daily-briefing (route contract)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _make_briefing_response(cached: bool = True, stale: bool = False):
    """Build a mock BriefingResponse."""
    from app.schemas.briefing import BriefingResponse

    return BriefingResponse(
        content="Good morning! Here is your daily briefing.",
        cached=cached,
        stale=stale,
        date=date.today(),
        generated_at=datetime.now(timezone.utc),
    )


class TestBriefingRoute:
    """Integration tests for GET /briefing using FastAPI TestClient."""

    def test_get_briefing_returns_200(self, client):
        """Valid user_id → 200 with BriefingResponse shape."""
        from app.services import briefing_service

        user_id = str(uuid4())
        mock_response = _make_briefing_response(cached=True, stale=False)

        with patch.object(
            briefing_service,
            "get_or_generate",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = client.get(f"/briefing?user_id={user_id}")

        assert response.status_code == 200
        body = response.json()
        assert "content" in body
        assert "cached" in body
        assert "stale" in body
        assert body["cached"] is True
        assert body["stale"] is False

    def test_get_briefing_missing_user_id_returns_422(self, client):
        """Missing user_id query param → 422 Unprocessable Entity."""
        response = client.get("/briefing")
        assert response.status_code == 422

    def test_get_briefing_cached_false_on_miss(self, client):
        """Cache miss → cached=False, stale=False."""
        from app.services import briefing_service

        user_id = str(uuid4())
        mock_response = _make_briefing_response(cached=False, stale=False)

        with patch.object(
            briefing_service,
            "get_or_generate",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = client.get(f"/briefing?user_id={user_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["cached"] is False
        assert body["stale"] is False

    def test_get_briefing_stale_serve(self, client):
        """Stale serve → cached=True, stale=True."""
        from app.services import briefing_service

        user_id = str(uuid4())
        mock_response = _make_briefing_response(cached=True, stale=True)

        with patch.object(
            briefing_service,
            "get_or_generate",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = client.get(f"/briefing?user_id={user_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["cached"] is True
        assert body["stale"] is True
