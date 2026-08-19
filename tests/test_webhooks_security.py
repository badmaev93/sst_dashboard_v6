from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_webhook_missing_key():
    response = client.post("/api/webhooks/agent/insight", json={
        "agent_name": "TestBot",
        "severity": "info",
        "title": "Test Title",
        "body": "Test Body",
        "metadata": {}
    })
    assert response.status_code == 403


def test_webhook_invalid_key():
    response = client.post(
        "/api/webhooks/agent/insight",
        headers={"X-Agent-Key": "wrong_key"},
        json={
            "agent_name": "TestBot",
            "severity": "info",
            "title": "Test Title",
            "body": "Test Body",
            "metadata": {}
        }
    )
    assert response.status_code == 403


def test_webhook_empty_configured_key():
    with patch("config.AGENT_API_KEY", ""):
        response = client.post(
            "/api/webhooks/agent/insight",
            headers={"X-Agent-Key": ""},
            json={
                "agent_name": "TestBot",
                "severity": "info",
                "title": "Test Title",
                "body": "Test Body",
                "metadata": {}
            }
        )
        assert response.status_code == 403


def test_webhook_valid_key():
    with patch("config.AGENT_API_KEY", "secret123"), \
         patch("db.pool") as mock_pool:
        mock_pool.fetchrow = AsyncMock(return_value={"id": 1})
        response = client.post(
            "/api/webhooks/agent/insight",
            headers={"X-Agent-Key": "secret123"},
            json={
                "agent_name": "TestBot",
                "severity": "info",
                "title": "Test Title",
                "body": "Test Body",
                "metadata": {}
            }
        )
        assert response.status_code == 200
        assert response.json() == {"id": 1, "status": "accepted"}
