from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import db
from app import app

client = TestClient(app)

@pytest.fixture
def mock_db_pool():
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    db.pool = old_pool

@patch("routers.webhooks.AGENT_API_KEY", "configured-secret-key-123")
def test_webhook_authorized_success(mock_db_pool):
    mock_db = mock_db_pool
    mock_db.fetchrow.return_value = {"id": 101}

    payload = {
        "agent_name": "SentinelBot",
        "severity": "info",
        "title": "Security Check Clean",
        "body": "No issues found in system scan.",
        "metadata": {"scanned_items": 42}
    }

    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload,
        headers={"X-Agent-Key": "configured-secret-key-123"}
    )
    assert response.status_code == 200
    assert response.json() == {"id": 101, "status": "accepted"}

@patch("routers.webhooks.AGENT_API_KEY", "configured-secret-key-123")
def test_webhook_invalid_key_rejected():
    payload = {
        "agent_name": "SentinelBot",
        "severity": "info",
        "title": "Security Check Clean",
        "body": "No issues found in system scan."
    }

    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload,
        headers={"X-Agent-Key": "wrong-secret-key"}
    )
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

@patch("routers.webhooks.AGENT_API_KEY", "configured-secret-key-123")
def test_webhook_missing_key_rejected():
    payload = {
        "agent_name": "SentinelBot",
        "severity": "info",
        "title": "Security Check Clean",
        "body": "No issues found in system scan."
    }

    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload
    )
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

@patch("routers.webhooks.AGENT_API_KEY", "")
def test_webhook_empty_config_fails_closed_with_empty_header():
    payload = {
        "agent_name": "SentinelBot",
        "severity": "info",
        "title": "Security Check Clean",
        "body": "No issues found."
    }

    # Even if client passes an empty key, and configured key is empty, it must fail closed
    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload,
        headers={"X-Agent-Key": ""}
    )
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

@patch("routers.webhooks.AGENT_API_KEY", "")
def test_webhook_empty_config_fails_closed_with_missing_header():
    payload = {
        "agent_name": "SentinelBot",
        "severity": "info",
        "title": "Security Check Clean",
        "body": "No issues found."
    }

    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload
    )
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]
