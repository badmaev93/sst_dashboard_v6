import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
import routers.webhooks
import db

client = TestClient(app)

@pytest.fixture
def mock_db():
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    db.pool = old_pool

def test_webhook_unauthorized_no_key(mock_db, monkeypatch):
    monkeypatch.setattr(routers.webhooks, "AGENT_API_KEY", "secure_secret_key")
    # No header
    response = client.post("/api/webhooks/agent/insight", json={
        "agent_name": "test_agent",
        "title": "Test Title",
        "body": "Test Body"
    })
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

def test_webhook_unauthorized_wrong_key(mock_db, monkeypatch):
    monkeypatch.setattr(routers.webhooks, "AGENT_API_KEY", "secure_secret_key")
    # Incorrect header
    response = client.post("/api/webhooks/agent/insight", json={
        "agent_name": "test_agent",
        "title": "Test Title",
        "body": "Test Body"
    }, headers={"X-Agent-Key": "wrong_key"})
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

def test_webhook_empty_key_fails_even_if_configured_empty(mock_db, monkeypatch):
    # If the app has an empty AGENT_API_KEY configured, sending an empty key header must still be rejected.
    monkeypatch.setattr(routers.webhooks, "AGENT_API_KEY", "")
    response = client.post("/api/webhooks/agent/insight", json={
        "agent_name": "test_agent",
        "title": "Test Title",
        "body": "Test Body"
    }, headers={"X-Agent-Key": ""})
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

def test_webhook_empty_key_fails_if_key_missing_from_header(mock_db, monkeypatch):
    monkeypatch.setattr(routers.webhooks, "AGENT_API_KEY", "")
    response = client.post("/api/webhooks/agent/insight", json={
        "agent_name": "test_agent",
        "title": "Test Title",
        "body": "Test Body"
    })
    assert response.status_code == 403
    assert "Invalid agent key" in response.json()["detail"]

def test_webhook_authorized_success(mock_db, monkeypatch):
    monkeypatch.setattr(routers.webhooks, "AGENT_API_KEY", "secure_secret_key")
    mock_db.fetchrow.return_value = {"id": 42}

    response = client.post("/api/webhooks/agent/insight", json={
        "agent_name": "test_agent",
        "title": "Test Title",
        "body": "Test Body",
        "severity": "info",
        "metadata": {"test": "data"}
    }, headers={"X-Agent-Key": "secure_secret_key"})

    assert response.status_code == 200
    assert response.json() == {"id": 42, "status": "accepted"}
