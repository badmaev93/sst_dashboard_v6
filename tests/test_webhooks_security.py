from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import db
from app import app

client = TestClient(app)

@pytest.fixture
def mock_db():
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    db.pool = old_pool

def test_webhook_missing_key():
    response = client.post("/api/webhooks/agent/insight", json={
        "agent_name": "TestAgent",
        "title": "Test Title",
        "body": "Test Body",
        "severity": "info",
        "metadata": None
    })
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

def test_webhook_invalid_key():
    with patch("routers.webhooks.AGENT_API_KEY", "secret_key"):
        response = client.post(
            "/api/webhooks/agent/insight",
            headers={"X-Agent-Key": "wrong_key"},
            json={
                "agent_name": "TestAgent",
                "title": "Test Title",
                "body": "Test Body",
                "severity": "info",
                "metadata": None
            }
        )
        assert response.status_code == 403
        assert "Invalid agent key" in response.json()["detail"]

def test_webhook_unconfigured_key_fails_closed():
    # When AGENT_API_KEY is empty/None in the configuration
    with patch("routers.webhooks.AGENT_API_KEY", ""):
        # Caller tries with an empty key
        response = client.post(
            "/api/webhooks/agent/insight",
            headers={"X-Agent-Key": ""},
            json={
                "agent_name": "TestAgent",
                "title": "Test Title",
                "body": "Test Body",
                "severity": "info",
                "metadata": None
            }
        )
        assert response.status_code == 403

        # Caller tries with some key
        response2 = client.post(
            "/api/webhooks/agent/insight",
            headers={"X-Agent-Key": "some_key"},
            json={
                "agent_name": "TestAgent",
                "title": "Test Title",
                "body": "Test Body",
                "severity": "info",
                "metadata": None
            }
        )
        assert response2.status_code == 403

def test_webhook_valid_key_insight(mock_db):
    mock_db.fetchrow.return_value = {"id": 123}
    with patch("routers.webhooks.AGENT_API_KEY", "super_secret_key"):
        response = client.post(
            "/api/webhooks/agent/insight",
            headers={"X-Agent-Key": "super_secret_key"},
            json={
                "agent_name": "TestAgent",
                "title": "Test Title",
                "body": "Test Body",
                "severity": "info",
                "metadata": None
            }
        )
        assert response.status_code == 200
        assert response.json() == {"id": 123, "status": "accepted"}

def test_webhook_valid_key_status(mock_db):
    mock_db.fetchrow.return_value = {"id": 124}
    with patch("routers.webhooks.AGENT_API_KEY", "super_secret_key"):
        response = client.post(
            "/api/webhooks/agent/status",
            headers={"X-Agent-Key": "super_secret_key"},
            json={
                "agent_name": "TestAgent",
                "title": "Test Status",
                "body": "Test Body",
                "severity": "info",
                "metadata": None
            }
        )
        assert response.status_code == 200
        assert response.json() == {"id": 124, "status": "accepted"}

def test_webhook_valid_key_anomaly(mock_db):
    mock_db.fetchrow.return_value = {"id": 125}
    with patch("routers.webhooks.AGENT_API_KEY", "super_secret_key"):
        response = client.post(
            "/api/webhooks/agent/anomaly",
            headers={"X-Agent-Key": "super_secret_key"},
            json={
                "agent_name": "TestAgent",
                "title": "Test Anomaly",
                "body": "Test Body",
                "severity": "critical",
                "metadata": None
            }
        )
        assert response.status_code == 200
        assert response.json() == {"id": 125, "status": "accepted"}
