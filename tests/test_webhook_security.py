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
    # Mock pool.fetchrow to return a mock row for inserted activity
    db.pool.fetchrow.return_value = {"id": 42}
    yield db.pool
    db.pool = old_pool

def test_webhook_unauthorized_when_key_is_empty(mock_db):
    # Case 1: AGENT_API_KEY is empty string
    with patch("routers.webhooks.AGENT_API_KEY", ""):
        # Request with empty key
        response = client.post(
            "/api/webhooks/agent/insight",
            json={"agent_name": "test_agent", "title": "Test Insight", "body": "Hello", "severity": "info", "metadata": None},
            headers={"X-Agent-Key": ""}
        )
        assert response.status_code == 403
        assert "Invalid agent key" in response.json()["detail"]

        # Request with missing key
        response = client.post(
            "/api/webhooks/agent/insight",
            json={"agent_name": "test_agent", "title": "Test Insight", "body": "Hello", "severity": "info", "metadata": None}
        )
        assert response.status_code == 403

def test_webhook_unauthorized_when_key_is_none(mock_db):
    # Case 2: AGENT_API_KEY is None
    with patch("routers.webhooks.AGENT_API_KEY", None):
        response = client.post(
            "/api/webhooks/agent/insight",
            json={"agent_name": "test_agent", "title": "Test Insight", "body": "Hello", "severity": "info", "metadata": None},
            headers={"X-Agent-Key": ""}
        )
        assert response.status_code == 403

def test_webhook_authorized_when_key_is_valid(mock_db):
    # Case 3: AGENT_API_KEY is configured and correct key is provided
    with patch("routers.webhooks.AGENT_API_KEY", "secure_secret_token_abc_123"):
        response = client.post(
            "/api/webhooks/agent/insight",
            json={"agent_name": "test_agent", "title": "Test Insight", "body": "Hello", "severity": "info", "metadata": None},
            headers={"X-Agent-Key": "secure_secret_token_abc_123"}
        )
        assert response.status_code == 200
        assert response.json() == {"id": 42, "status": "accepted"}

def test_webhook_unauthorized_when_key_is_incorrect(mock_db):
    # Case 4: AGENT_API_KEY is configured but incorrect key is provided
    with patch("routers.webhooks.AGENT_API_KEY", "secure_secret_token_abc_123"):
        response = client.post(
            "/api/webhooks/agent/insight",
            json={"agent_name": "test_agent", "title": "Test Insight", "body": "Hello", "severity": "info", "metadata": None},
            headers={"X-Agent-Key": "wrong_key"}
        )
        assert response.status_code == 403
