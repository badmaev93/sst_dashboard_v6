import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app import app
import db

client = TestClient(app)

@pytest.fixture
def mock_db():
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    db.pool = old_pool

def test_webhooks_no_agent_key_unconfigured(mock_db):
    """
    If the server's AGENT_API_KEY is not configured (empty string or None),
    requests with or without client keys should both be rejected.
    """
    with patch("routers.webhooks.AGENT_API_KEY", ""):
        # Client sends no key
        response = client.post("/api/webhooks/agent/insight", json={
            "agent_name": "TestAgent",
            "title": "Anomaly detected",
            "body": None,
            "severity": "info",
            "metadata": None
        })
        assert response.status_code == 403
        assert "Invalid agent key" in response.json()["detail"]

        # Client sends an empty key
        response = client.post("/api/webhooks/agent/insight", json={
            "agent_name": "TestAgent",
            "title": "Anomaly detected",
            "body": None,
            "severity": "info",
            "metadata": None
        }, headers={"X-Agent-Key": ""})
        assert response.status_code == 403
        assert "Invalid agent key" in response.json()["detail"]

        # Client sends some random key
        response = client.post("/api/webhooks/agent/insight", json={
            "agent_name": "TestAgent",
            "title": "Anomaly detected",
            "body": None,
            "severity": "info",
            "metadata": None
        }, headers={"X-Agent-Key": "some-random-key"})
        assert response.status_code == 403
        assert "Invalid agent key" in response.json()["detail"]


def test_webhooks_with_invalid_key(mock_db):
    """
    If AGENT_API_KEY is configured on the server, requests with an invalid key should be rejected.
    """
    with patch("routers.webhooks.AGENT_API_KEY", "secure-agent-key-123"):
        # Client sends wrong key
        response = client.post("/api/webhooks/agent/insight", json={
            "agent_name": "TestAgent",
            "title": "Anomaly detected",
            "body": None,
            "severity": "info",
            "metadata": None
        }, headers={"X-Agent-Key": "wrong-key"})
        assert response.status_code == 403
        assert "Invalid agent key" in response.json()["detail"]

        # Client sends no key
        response = client.post("/api/webhooks/agent/insight", json={
            "agent_name": "TestAgent",
            "title": "Anomaly detected",
            "body": None,
            "severity": "info",
            "metadata": None
        })
        assert response.status_code == 403
        assert "Invalid agent key" in response.json()["detail"]


def test_webhooks_authorized_success(mock_db):
    """
    If AGENT_API_KEY is configured and the client sends the correct key,
    the request should be successfully authorized and processed.
    """
    mock_db.fetchrow.return_value = {"id": 42}
    with patch("routers.webhooks.AGENT_API_KEY", "secure-agent-key-123"):
        payload = {
            "agent_name": "TestAgent",
            "title": "Anomaly detected",
            "body": "Detailed description of the issue.",
            "severity": "info",
            "metadata": {"test_key": "test_val"}
        }
        response = client.post("/api/webhooks/agent/insight", json=payload, headers={"X-Agent-Key": "secure-agent-key-123"})
        assert response.status_code == 200
        assert response.json() == {"id": 42, "status": "accepted"}


def test_webhooks_anomaly_critical_triggers_notification(mock_db):
    """
    If a critical anomaly is posted with the correct key,
    the endpoint should attempt to notify supervisors.
    """
    mock_db.fetchrow.return_value = {"id": 100}
    with patch("routers.webhooks.AGENT_API_KEY", "secure-agent-key-123"), \
         patch("services.notification.notify_supervisors", AsyncMock()) as mock_notify:
        payload = {
            "agent_name": "TestAgent",
            "title": "Critical issue!",
            "body": None,
            "severity": "critical",
            "metadata": None
        }
        response = client.post("/api/webhooks/agent/anomaly", json=payload, headers={"X-Agent-Key": "secure-agent-key-123"})
        assert response.status_code == 200
        assert response.json() == {"id": 100, "status": "accepted"}
        mock_notify.assert_called_once()
