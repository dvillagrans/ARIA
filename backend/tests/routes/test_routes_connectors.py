"""
TDD tests for connector sync routes — Phase 4.

Tests:
- POST /connectors/sync/github returns SyncResult shape
- POST /connectors/sync/gmail returns SyncResult shape
- POST /connectors/sync/calendar returns SyncResult shape
- All routes reject missing API key (401)
"""

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure the ingest API key env var is set BEFORE app import
os.environ["INGEST_API_KEY"] = "test-ingest-key"


def _make_test_app() -> FastAPI:
    """Create a test app with mocked providers."""
    from app.main import create_app
    from app.core.deps import get_llm, get_embedder, get_async_supabase

    mock_llm = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embed = AsyncMock(return_value=[0.1] * 1536)
    mock_db = MagicMock()

    async def _mock_supabase():
        return mock_db

    app = create_app()
    app.dependency_overrides[get_llm] = lambda: mock_llm
    app.dependency_overrides[get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_async_supabase] = _mock_supabase
    return app


@pytest.fixture(scope="module")
def connector_client():
    """TestClient with mocked providers."""
    app = _make_test_app()
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Auth: all connector routes reject missing API key
# ---------------------------------------------------------------------------

def test_github_sync_rejects_missing_api_key(connector_client):
    """POST /connectors/sync/github with no X-API-Key → 401."""
    response = connector_client.post("/connectors/sync/github")
    assert response.status_code == 401


def test_gmail_sync_rejects_missing_api_key(connector_client):
    """POST /connectors/sync/gmail with no X-API-Key → 401."""
    response = connector_client.post("/connectors/sync/gmail")
    assert response.status_code == 401


def test_calendar_sync_rejects_missing_api_key(connector_client):
    """POST /connectors/sync/calendar with no X-API-Key → 401."""
    response = connector_client.post("/connectors/sync/calendar")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GitHub sync returns SyncResult shape
# ---------------------------------------------------------------------------

def test_github_sync_returns_sync_result(connector_client):
    """POST /connectors/sync/github → 200 with {created/skipped/failed/errors}."""
    from app.connectors.base import SyncResult

    with patch("app.connectors.github.sync", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = SyncResult(created=2, skipped=1, failed=0, errors=[])

        response = connector_client.post(
            "/connectors/sync/github",
            json={"user_id": str(uuid.uuid4())},
            headers={"X-API-Key": "test-ingest-key"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "created" in body
    assert "skipped" in body
    assert "failed" in body
    assert "errors" in body
    assert body["created"] == 2
    assert body["skipped"] == 1


# ---------------------------------------------------------------------------
# Gmail sync returns SyncResult shape
# ---------------------------------------------------------------------------

def test_gmail_sync_returns_sync_result(connector_client):
    """POST /connectors/sync/gmail → 200 with {created/skipped/failed/errors}."""
    from app.connectors.base import SyncResult

    with patch("app.connectors.gmail.sync", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = SyncResult(created=5, skipped=0, failed=0, errors=[])

        response = connector_client.post(
            "/connectors/sync/gmail",
            json={"user_id": str(uuid.uuid4())},
            headers={"X-API-Key": "test-ingest-key"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 5


def test_calendar_sync_returns_sync_result(connector_client):
    """POST /connectors/sync/calendar → 200 with {created/skipped/failed/errors}."""
    from app.connectors.base import SyncResult

    with patch("app.connectors.calendar.sync", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = SyncResult(created=3, skipped=0, failed=0, errors=[])

        response = connector_client.post(
            "/connectors/sync/calendar",
            json={"user_id": str(uuid.uuid4())},
            headers={"X-API-Key": "test-ingest-key"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 3
