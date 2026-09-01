from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app import app
import db

client = TestClient(app)

PAYLOAD = {
    "agent_name": "TestBot",
    "severity": "info",
    "title": "Test Insight",
    "body": "Detailed insight body",
    "metadata": None,
}

def test_webhook_missing_key():
    response = client.post("/api/webhooks/agent/insight", json=PAYLOAD)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid agent key"


def test_webhook_invalid_key():
    response = client.post(
        "/api/webhooks/agent/insight",
        json=PAYLOAD,
        headers={"X-Agent-Key": "invalid_secret_key_123"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid agent key"


def test_webhook_unconfigured_secret():
    with patch("routers.webhooks.AGENT_API_KEY", ""):
        response = client.post(
            "/api/webhooks/agent/insight",
            json=PAYLOAD,
            headers={"X-Agent-Key": "some_key"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid agent key"


def test_webhook_valid_key():
    valid_key = "secret_agent_key_xyz"
    old_pool = db.pool
    db.pool = AsyncMock()
    db.pool.fetchrow.return_value = {"id": 100}

    try:
        with patch("routers.webhooks.AGENT_API_KEY", valid_key):
            response = client.post(
                "/api/webhooks/agent/insight",
                json=PAYLOAD,
                headers={"X-Agent-Key": valid_key}
            )
            assert response.status_code == 200
            assert response.json() == {"id": 100, "status": "accepted"}
    finally:
        db.pool = old_pool
