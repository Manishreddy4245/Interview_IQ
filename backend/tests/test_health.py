from unittest.mock import patch
from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    """Test that GET /health returns 200 and expected service status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "interviewiq-backend"
    assert "environment" in data


def test_database_health_unconfigured(client: TestClient):
    """
    Test that GET /health/db returns 503 and clear unconfigured diagnostic
    when MONGODB_URI is absent.
    """
    response = client.get("/health/db")
    data = response.json()
    assert response.status_code == 503
    assert data["status"] == "unconfigured"
    assert "MONGODB_URI is not configured" in data["detail"]
    assert data["database"] == "interviewiq"


def test_groq_health_unconfigured(client: TestClient):
    """
    Test that GET /health/groq returns 503 and clear unconfigured diagnostic
    when GROQ_API_KEY is absent.
    """
    with patch("app.core.config.settings.GROQ_API_KEY", None):
        response = client.get("/health/groq")
        data = response.json()
        assert response.status_code == 503
        assert data["configured"] is False
        assert data["status"] == "unconfigured"
        assert "GROQ_API_KEY is missing" in data["detail"]


def test_cors_headers(client: TestClient):
    """Test that CORS headers allow http://localhost:3000 origin."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
