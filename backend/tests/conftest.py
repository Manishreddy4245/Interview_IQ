from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch, request):
    """
    Ensure unit tests run in a hermetic environment without unmocked
    live external network requests to MongoDB Atlas unless marked live_atlas.
    """
    if request.node.get_closest_marker("live_atlas") is None:
        monkeypatch.setattr(settings, "MONGODB_URI", None)
    yield


@pytest.fixture
def client():
    """Synchronous test client for FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client
