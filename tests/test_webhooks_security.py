import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
import routers.webhooks
import db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    # Save original values
    orig_api_key = getattr(routers.webhooks, "AGENT_API_KEY", "")
    orig_pool = db.pool

    db.pool = AsyncMock()

    yield

    # Restore original values
    routers.webhooks.AGENT_API_KEY = orig_api_key
    db.pool = orig_pool

def test_webhooks_unconfigured_api_key_rejects_all():
    # Set server-side key to empty
    routers.webhooks.AGENT_API_KEY = ""

    payload = {
        "agent_name": "sentinel",
        "title": "Security Check",
        "body": "This is a security check.",
        "severity": "info",
        "metadata": {}
    }

    # Case 1: Missing X-Agent-Key header
    response = client.post("/api/webhooks/agent/insight", json=payload)
    assert response.status_code == 403

    # Case 2: Empty X-Agent-Key header
    response = client.post("/api/webhooks/agent/insight", json=payload, headers={"X-Agent-Key": ""})
    assert response.status_code == 403

    # Case 3: Random X-Agent-Key header
    response = client.post("/api/webhooks/agent/insight", json=payload, headers={"X-Agent-Key": "somekey"})
    assert response.status_code == 403

def test_webhooks_configured_api_key_valid_and_invalid():
    # Set server-side key to a test key
    routers.webhooks.AGENT_API_KEY = "secure_test_agent_key_123"

    payload = {
        "agent_name": "sentinel",
        "title": "Security Check",
        "body": "This is a security check.",
        "severity": "info",
        "metadata": {}
    }

    db.pool.fetchrow.return_value = {"id": 42}

    # Case 1: Correct key
    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload,
        headers={"X-Agent-Key": "secure_test_agent_key_123"}
    )
    assert response.status_code == 200
    assert response.json() == {"id": 42, "status": "accepted"}

    # Case 2: Incorrect key
    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload,
        headers={"X-Agent-Key": "wrong_key"}
    )
    assert response.status_code == 403

    # Case 3: Empty key
    response = client.post(
        "/api/webhooks/agent/insight",
        json=payload,
        headers={"X-Agent-Key": ""}
    )
    assert response.status_code == 403

    # Case 4: Missing key
    response = client.post("/api/webhooks/agent/insight", json=payload)
    assert response.status_code == 403

def test_webhooks_endpoints_all_secured():
    routers.webhooks.AGENT_API_KEY = "secure_test_agent_key_123"
    payload = {
        "agent_name": "sentinel",
        "title": "Security Check",
        "body": "This is a security check.",
        "severity": "info",
        "metadata": {}
    }
    db.pool.fetchrow.return_value = {"id": 100}

    # Check all three agent endpoints reject bad keys and accept correct keys
    endpoints = [
        "/api/webhooks/agent/insight",
        "/api/webhooks/agent/status",
        "/api/webhooks/agent/anomaly"
    ]

    for endpoint in endpoints:
        # Invalid key -> 403
        res = client.post(endpoint, json=payload, headers={"X-Agent-Key": "invalid"})
        assert res.status_code == 403

        # Valid key -> 200
        res = client.post(endpoint, json=payload, headers={"X-Agent-Key": "secure_test_agent_key_123"})
        assert res.status_code == 200
        assert res.json() == {"id": 100, "status": "accepted"}
