from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import db
from app import app

client = TestClient(app)

def test_webhooks_missing_key():
    # Requests without X-Agent-Key should return 403
    payload = {
        "agent_name": "TestBot",
        "title": "Test Insight",
        "body": "Test Body",
        "severity": "info"
    }
    response = client.post("/api/webhooks/agent/insight", json=payload)
    assert response.status_code == 403

    response = client.post("/api/webhooks/agent/status", json=payload)
    assert response.status_code == 403

    response = client.post("/api/webhooks/agent/anomaly", json=payload)
    assert response.status_code == 403


def test_webhooks_invalid_key():
    # Requests with invalid X-Agent-Key should return 403
    payload = {
        "agent_name": "TestBot",
        "title": "Test Insight",
        "body": "Test Body",
        "severity": "info"
    }
    headers = {"X-Agent-Key": "wrong-key"}
    response = client.post("/api/webhooks/agent/insight", json=payload, headers=headers)
    assert response.status_code == 403


def test_webhooks_empty_configured_key():
    # When AGENT_API_KEY is empty/None, requests should fail securely (403)
    payload = {
        "agent_name": "TestBot",
        "title": "Test Insight",
        "body": "Test Body",
        "severity": "info"
    }
    headers = {"X-Agent-Key": "some-key"}
    with patch("routers.webhooks.AGENT_API_KEY", ""):
        response = client.post("/api/webhooks/agent/insight", json=payload, headers=headers)
        assert response.status_code == 403


def test_webhooks_valid_key():
    # Valid key should allow the webhook request
    payload = {
        "agent_name": "TestBot",
        "title": "Test Insight",
        "body": "Test Body",
        "severity": "info"
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    db.pool.fetchrow.return_value = {"id": 1}

    try:
        with patch("routers.webhooks.AGENT_API_KEY", "secret-agent-key"):
            headers = {"X-Agent-Key": "secret-agent-key"}
            response = client.post("/api/webhooks/agent/insight", json=payload, headers=headers)
            assert response.status_code == 200
            assert response.json()["status"] == "accepted"
    finally:
        db.pool = old_pool
