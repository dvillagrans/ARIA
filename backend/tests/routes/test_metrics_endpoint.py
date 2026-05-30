"""
Tests for GET /metrics endpoint.

Spec requirement: returns 200, Content-Type text/plain; version=0.0.4,
body contains aria_ prefix metrics in Prometheus text exposition format.
"""


class TestMetricsEndpoint:
    """Tests for the /metrics endpoint."""

    def test_metrics_returns_200(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type(self, client):
        response = client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_body_contains_aria_prefix(self, client):
        response = client.get("/metrics")
        body = response.text
        # At least one aria_ metric should be present
        assert "aria_" in body

    def test_metrics_contains_http_requests_metric(self, client):
        response = client.get("/metrics")
        body = response.text
        # Counter names strip _total suffix in exposition format
        assert "aria_http_requests" in body

    def test_metrics_contains_http_duration_metric(self, client):
        response = client.get("/metrics")
        body = response.text
        assert "aria_http_request_duration_seconds" in body

    def test_metrics_not_tracked_by_middleware(self, client):
        """GET /metrics should not increment the HTTP request counter."""
        # Get the response first
        response = client.get("/metrics")
        assert response.status_code == 200
        # The middleware excludes /metrics, so this request should not
        # appear in the counter with endpoint="/metrics"
        body = response.text
        # Verify the body doesn't contain a line with endpoint="/metrics"
        # for the current request
        for line in body.split("\n"):
            if 'aria_http_requests' in line and 'endpoint="/metrics"' in line:
                # This would mean the middleware tracked /metrics
                assert False, "/metrics should not be tracked by middleware"
