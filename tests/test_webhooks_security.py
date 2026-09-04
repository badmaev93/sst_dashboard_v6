from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app import app
import db

client = TestClient(app)

INSIGHT_PAYLOAD = {
    "agent_name": "TestAgent",
    "severity": "info",
    "title": "Test Title",
    "body": "Test Body",
    "metadata": {"test": "data"},
}

def test_webhook_missing_key():
    response = client.post("/api/webhooks/agent/insight", json=INSIGHT_PAYLOAD)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid agent key"

def test_webhook_invalid_key():
    response = client.post(
        "/api/webhooks/agent/insight",
        headers={"X-Agent-Key": "wrong-key"},
        json=INSIGHT_PAYLOAD,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid agent key"

def test_webhook_empty_key():
    response = client.post(
        "/api/webhooks/agent/insight",
        headers={"X-Agent-Key": ""},
        json=INSIGHT_PAYLOAD,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid agent key"

def test_webhook_unconfigured_server_key():
    with patch("routers.webhooks.AGENT_API_KEY", ""):
        response = client.post(
            "/api/webhooks/agent/insight",
            headers={"X-Agent-Key": ""},
            json=INSIGHT_PAYLOAD,
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid agent key"

def test_webhook_valid_key():
    old_pool = db.pool
    mock_pool = AsyncMock()
    mock_pool.fetchrow.return_value = {"id": 42}
    db.pool = mock_pool

    try:
        with patch("routers.webhooks.AGENT_API_KEY", "secret-agent-key-123"):
            response = client.post(
                "/api/webhooks/agent/insight",
                headers={"X-Agent-Key": "secret-agent-key-123"},
                json=INSIGHT_PAYLOAD,
            )
            assert response.status_code == 200
            assert response.json() == {"id": 42, "status": "accepted"}
    finally:
        db.pool = old_pool
