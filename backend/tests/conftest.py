"""
Pytest configuration and shared fixtures.
"""

import os

import pytest
from fastapi.testclient import TestClient

# Provide all required env vars before the app is imported so Settings
# does not raise ValidationError during test collection.
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("DEEPSEEK_API_KEY", "test-deepseek-key")
os.environ.setdefault("DEEPINFRA_API_KEY", "test-deepinfra-key")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")


@pytest.fixture(scope="session")
def client():
    """Return a synchronous TestClient for the FastAPI app."""
    from app.main import app

    with TestClient(app) as c:
        yield c
