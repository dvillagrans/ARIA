"""
Tests for the CORS_ALLOWED_ORIGINS override in the app factory.

Spec requirement: the backend allows only http://localhost:3000 by default and
honours a comma-separated CORS_ALLOWED_ORIGINS override (see app/main.py).
"""

from fastapi.testclient import TestClient

from app.main import create_app

LOCALHOST_ORIGIN = "http://localhost:3000"


def _preflight(client: TestClient, origin: str):
    """Send a CORS preflight request for ``origin`` to GET /health."""
    return client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


class TestCorsAllowedOrigins:
    """Tests for the CORS_ALLOWED_ORIGINS env override."""

    def test_default_allows_localhost_only(self, monkeypatch):
        """Without the env var, only the localhost dev origin is allowed."""
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
        app = create_app()
        client = TestClient(app)

        allowed = _preflight(client, LOCALHOST_ORIGIN)
        rejected = _preflight(client, "https://evil.example")

        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == LOCALHOST_ORIGIN
        assert "access-control-allow-origin" not in rejected.headers

    def test_comma_separated_override_is_honoured(self, monkeypatch):
        """A comma-separated override replaces the default and is trimmed."""
        monkeypatch.setenv(
            "CORS_ALLOWED_ORIGINS",
            "https://app.example, https://admin.example",
        )
        app = create_app()
        client = TestClient(app)

        for origin in ("https://app.example", "https://admin.example"):
            response = _preflight(client, origin)
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin

        # The override replaces the default rather than extending it.
        rejected = _preflight(client, LOCALHOST_ORIGIN)
        assert "access-control-allow-origin" not in rejected.headers
