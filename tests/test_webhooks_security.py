import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
import routers.webhooks as webhooks_module
import db

client = TestClient(app)

@pytest.fixture
def mock_db_pool():
    old_pool = db.pool
    db.pool = AsyncMock()
    # Mock row return for database operations
    db.pool.fetchrow.return_value = {"id": 42}
    yield db.pool
    db.pool = old_pool

def test_webhook_with_valid_api_key(mock_db_pool, monkeypatch):
    # Set a mock API key
    monkeypatch.setattr(webhooks_module, "AGENT_API_KEY", "super_secure_key_123")

    payload = {
        "agent_name": "SentinelAgent",
        "title": "Security Check",
        "body": "System scanning has started",
        "severity": "info",
        "metadata": {}
    }

    # Request with valid key
    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload,
        headers={"X-Agent-Key": "super_secure_key_123"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["id"] == 42

def test_webhook_with_invalid_api_key(mock_db_pool, monkeypatch):
    monkeypatch.setattr(webhooks_module, "AGENT_API_KEY", "super_secure_key_123")

    payload = {
        "agent_name": "SentinelAgent",
        "title": "Security Check",
        "body": "System scanning has started",
        "severity": "info"
    }

    # Request with invalid key
    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload,
        headers={"X-Agent-Key": "wrong_key"}
    )
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

def test_webhook_with_missing_key_header(mock_db_pool, monkeypatch):
    monkeypatch.setattr(webhooks_module, "AGENT_API_KEY", "super_secure_key_123")

    payload = {
        "agent_name": "SentinelAgent",
        "title": "Security Check",
        "severity": "info"
    }

    # Request with missing header
    response = client.post("/api/webhooks/agent/insight", json=payload)
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

def test_webhook_empty_key_fails_closed(mock_db_pool, monkeypatch):
    # If AGENT_API_KEY is not set or empty, all requests should fail closed (yield 403)
    monkeypatch.setattr(webhooks_module, "AGENT_API_KEY", "")

    payload = {
        "agent_name": "SentinelAgent",
        "title": "Security Check",
        "severity": "info"
    }

    # Even if key header is empty, it shouldn't bypass authentication
    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload,
        headers={"X-Agent-Key": ""}
    )
    assert response.status_code == 403

    # Even if key is missing, it shouldn't bypass
    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload
    )
    assert response.status_code == 403
