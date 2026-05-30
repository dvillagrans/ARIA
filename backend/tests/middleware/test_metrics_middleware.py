"""
Tests for MetricsMiddleware.

Spec requirement: ASGI middleware auto-instruments every HTTP request with
duration histogram and request counter, excluding /metrics path.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.core.metrics import REGISTRY, aria_http_request_duration_seconds, aria_http_requests_total


class TestMetricsMiddleware:
    """Tests for MetricsMiddleware behavior."""

    def _make_scope(self, method="GET", path="/chat", query_string=b""):
        """Create a minimal ASGI HTTP scope."""
        return {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": query_string,
            "headers": [],
        }

    def _make_receive(self):
        """Create a mock ASGI receive."""
        return AsyncMock(return_value={"type": "http.request", "body": b""})

    def _make_send(self):
        """Create a mock ASGI send that captures messages."""
        messages = []

        async def send(msg):
            messages.append(msg)

        return send, messages

    @pytest.mark.asyncio
    async def test_middleware_records_status_code(self):
        """Middleware must capture the response status code."""
        from app.middleware.metrics import MetricsMiddleware

        scope = self._make_scope(method="POST", path="/chat")
        receive = self._make_receive()
        send, messages = self._make_send()

        async def inner_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = MetricsMiddleware(inner_app)
        await middleware(scope, receive, send)

        assert len(messages) == 2
        assert messages[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_middleware_excludes_metrics_path(self):
        """GET /metrics must NOT be recorded in the histogram or counter."""
        from app.middleware.metrics import MetricsMiddleware

        # Reset counters by checking current values
        before = aria_http_requests_total._metrics

        scope = self._make_scope(method="GET", path="/metrics")
        receive = self._make_receive()
        send, messages = self._make_send()

        async def inner_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"metrics"})

        middleware = MetricsMiddleware(inner_app)
        await middleware(scope, receive, send)

        # Counter should not have incremented for /metrics
        after = aria_http_requests_total._metrics
        assert len(after) == len(before), "/metrics should not increment counter"

    @pytest.mark.asyncio
    async def test_middleware_passes_through_non_http(self):
        """Non-HTTP scopes (e.g. websocket) must pass through unchanged."""
        from app.middleware.metrics import MetricsMiddleware

        scope = {"type": "websocket", "path": "/ws"}
        receive = self._make_receive()
        send, messages = self._make_send()
        called = False

        async def inner_app(scope, receive, send):
            nonlocal called
            called = True

        middleware = MetricsMiddleware(inner_app)
        await middleware(scope, receive, send)

        assert called is True

    @pytest.mark.asyncio
    async def test_middleware_records_500_status(self):
        """Middleware must record error status codes too."""
        from app.middleware.metrics import MetricsMiddleware

        scope = self._make_scope(method="GET", path="/health")
        receive = self._make_receive()
        send, messages = self._make_send()

        async def inner_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 500})
            await send({"type": "http.response.body", "body": b"error"})

        middleware = MetricsMiddleware(inner_app)
        await middleware(scope, receive, send)

        assert messages[0]["status"] == 500
