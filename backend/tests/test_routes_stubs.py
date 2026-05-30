"""
Tests for POST /chat route (schema validation layer).

Phase 1: POST /chat now requires user_id in the body (ChatRequest expanded).
The 501 stub behavior is replaced by full orchestration in Phase 1.
These tests verify the request schema contract (validation layer).

Note: POST /ingest stub tests (test_ingest_stub_*) were removed in Phase 4
when the route was replaced by the real implementation.
"""

import uuid


def test_chat_rejects_missing_message(client):
    """422 when message is absent."""
    response = client.post("/chat", json={"user_id": str(uuid.uuid4())})
    assert response.status_code == 422


def test_chat_rejects_missing_user_id(client):
    """422 when user_id is absent — Phase 1 schema requires it."""
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 422


def test_chat_rejects_empty_body(client):
    """422 when body is empty."""
    response = client.post("/chat", json={})
    assert response.status_code == 422


def test_ingest_rejects_missing_source(client):
    """422 when source is absent from IngestRequest (Phase 4 typed schema)."""
    response = client.post(
        "/ingest",
        json={"record_type": "task", "user_id": str(uuid.uuid4()), "title": "Buy milk"},
        headers={"X-API-Key": "test-ingest-key"},
    )
    assert response.status_code == 422
