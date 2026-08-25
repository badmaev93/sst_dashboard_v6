import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app import app
import config
import db

client = TestClient(app)

PAYLOAD = {
    "agent_name": "TestBot",
    "severity": "info",
    "title": "Test Event",
    "body": "Test message",
    "metadata": {"test": True}
}

def test_webhook_missing_key():
    response = client.post("/api/webhooks/agent/insight", json=PAYLOAD)
    assert response.status_code == 403

def test_webhook_invalid_key():
    with patch.object(config, "AGENT_API_KEY", "secret_key_123"):
        response = client.post(
            "/api/webhooks/agent/insight",
            json=PAYLOAD,
            headers={"X-Agent-Key": "wrong_key"}
        )
        assert response.status_code == 403

def test_webhook_empty_configured_key_denies():
    with patch.object(config, "AGENT_API_KEY", ""):
        response = client.post(
            "/api/webhooks/agent/insight",
            json=PAYLOAD,
            headers={"X-Agent-Key": ""}
        )
        assert response.status_code == 403

def test_webhook_valid_key_accepted():
    with patch.object(config, "AGENT_API_KEY", "valid_secret_key"):
        old_pool = db.pool
        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {"id": 42}
        db.pool = mock_pool
        try:
            response = client.post(
                "/api/webhooks/agent/insight",
                json=PAYLOAD,
                headers={"X-Agent-Key": "valid_secret_key"}
            )
            assert response.status_code == 200
            assert response.json() == {"id": 42, "status": "accepted"}
        finally:
            db.pool = old_pool
