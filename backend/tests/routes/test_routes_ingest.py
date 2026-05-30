"""
TDD RED tests for POST /ingest route — Phase 4.

These tests MUST fail until tasks 3.2 (route implementation) is done.

Scenarios:
- 401 when X-API-Key header is missing or wrong.
- 200 status="created" on valid request with correct key.
- 200 status="skipped" when external_id already exists (dedup).
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure the ingest API key env var is set for these tests BEFORE app import
os.environ["INGEST_API_KEY"] = "test-ingest-key"


@pytest.fixture(scope="module")
def ingest_client():
    """TestClient with INGEST_API_KEY set in environment."""
    from app.main import app
    with TestClient(app) as c:
        yield c


def _valid_ingest_payload(user_id: str | None = None) -> dict:
    return {
        "source": "github",
        "record_type": "task",
        "user_id": user_id or str(uuid.uuid4()),
        "title": "Review the PR",
        "external_id": "github:notification:42",
    }


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

def test_ingest_rejects_missing_api_key(ingest_client):
    """POST /ingest with no X-API-Key → 401."""
    response = ingest_client.post("/ingest", json=_valid_ingest_payload())
    assert response.status_code == 401


def test_ingest_rejects_wrong_api_key(ingest_client):
    """POST /ingest with wrong X-API-Key → 401."""
    response = ingest_client.post(
        "/ingest",
        json=_valid_ingest_payload(),
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Happy path: creates record
# ---------------------------------------------------------------------------

def test_ingest_creates_record(ingest_client):
    """POST /ingest with valid key and payload → 200, status='created'."""
    with patch("app.routes.ingest._ingest_one", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.return_value = ("created", str(uuid.uuid4()))

        response = ingest_client.post(
            "/ingest",
            json=_valid_ingest_payload(),
            headers={"X-API-Key": "test-ingest-key"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"


# ---------------------------------------------------------------------------
# Dedup: returns skipped
# ---------------------------------------------------------------------------

def test_ingest_dedups_by_external_id(ingest_client):
    """POST /ingest with duplicate external_id → 200, status='duplicate', record_id is UUID."""
    existing_id = str(uuid.uuid4())
    with patch("app.routes.ingest._ingest_one", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.return_value = ("duplicate", existing_id)

        response = ingest_client.post(
            "/ingest",
            json=_valid_ingest_payload(),
            headers={"X-API-Key": "test-ingest-key"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "duplicate"
    assert body["record_id"] == existing_id


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_ingest_rejects_invalid_record_type(ingest_client):
    """POST /ingest with invalid record_type → 422."""
    payload = _valid_ingest_payload()
    payload["record_type"] = "calendar_event"  # not in Literal
    response = ingest_client.post(
        "/ingest",
        json=payload,
        headers={"X-API-Key": "test-ingest-key"},
    )
    assert response.status_code == 422
