"""
MetricsMiddleware — ASGI middleware for automatic HTTP request instrumentation.

Wraps every HTTP request, recording:
- Duration in aria_http_request_duration_seconds Histogram
- Request count in aria_http_requests_total Counter
- Labels: method, endpoint (path), status code

Excludes the /metrics endpoint from instrumentation to avoid self-referential data.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.metrics import aria_http_request_duration_seconds, aria_http_requests_total

# Paths excluded from metrics instrumentation.
_EXCLUDED_PATHS = frozenset({"/metrics"})


class MetricsMiddleware:
    """ASGI middleware that auto-instruments HTTP request latency and count."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict,
        receive: Any,
        send: Any,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            status_str = str(status_code) if status_code else "0"

            labels = {"method": method, "endpoint": path, "status": status_str}

            if aria_http_request_duration_seconds is not None:
                aria_http_request_duration_seconds.labels(**labels).observe(duration)

            if aria_http_requests_total is not None:
                aria_http_requests_total.labels(**labels).inc()
