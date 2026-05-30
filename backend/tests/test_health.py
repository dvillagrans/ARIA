"""
Tests for GET /health endpoint.

Spec requirement: returns HTTP 200 with {"status": "ok", "metrics": "ready", "version": "<semver>"}.
Returns 503 when metrics are unavailable.
"""


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_body_has_status_ok(client):
    response = client.get("/health")
    body = response.json()
    assert body["status"] == "ok"


def test_health_body_has_metrics_ready(client):
    response = client.get("/health")
    body = response.json()
    assert body["metrics"] == "ready"


def test_health_body_has_version(client):
    response = client.get("/health")
    body = response.json()
    assert "version" in body
    assert body["version"] == "0.1.0"


def test_health_degraded_when_metrics_unavailable(client, monkeypatch):
    """
    Spec: when metrics registry is not initialized, /health returns 503
    with {"status": "degraded", "metrics": "unavailable"}.
    """
    from app.core import metrics

    # Temporarily mark metrics as uninitialized.
    monkeypatch.setattr(metrics, "_initialized", False)

    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["metrics"] == "unavailable"
    assert body["version"] == "0.1.0"
