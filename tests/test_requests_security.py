import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user
import db

client = TestClient(app)

def test_requests_unauthorized():
    # Verify that requesting without auth yields 401
    response = client.get("/api/monitoring/requests/")
    assert response.status_code == 401

    response = client.post("/api/monitoring/requests/", json={})
    assert response.status_code == 401

    response = client.put("/api/monitoring/requests/1", json={})
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth_observer():
    # User 1: observer role (not a supervisor)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "observer1",
        "full_name": "Шпачук Денис Иванович",
        "role": "observer",
        "is_active": True,
    }

    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool

    app.dependency_overrides.clear()
    db.pool = old_pool


@pytest.fixture
def mock_db_and_auth_supervisor():
    # User 2: supervisor role
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 2,
        "username": "supervisor1",
        "full_name": "Иванов Иван Иванович",
        "role": "supervisor",
        "is_active": True,
    }

    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool

    app.dependency_overrides.clear()
    db.pool = old_pool


def test_update_request_not_creator_observer(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Request created by user ID 99 (not the current observer with ID 1)
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,
        "title": "Old Title",
        "status": "draft",
    }

    response = client.put("/api/monitoring/requests/10", json={"title": "New Title"})
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_request_creator_observer_allowed(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Request created by user ID 1 (matches the current observer with ID 1)
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 1,
        "title": "Old Title",
        "status": "draft",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/requests/10", json={"title": "New Title"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_request_creator_observer_escalation_denied(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Request created by user ID 1
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 1,
        "title": "Old Title",
        "status": "draft",
    }

    # Attempting to change status to 'signed' (restricted to supervisors)
    response = client.put("/api/monitoring/requests/10", json={"status": "signed"})
    assert response.status_code == 403
    assert "Only supervisors" in response.json()["detail"]


def test_update_request_creator_observer_status_allowed(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Request created by user ID 1
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 1,
        "title": "Old Title",
        "status": "draft",
    }
    mock_db.execute.return_value = "UPDATE 1"

    # Non-supervisors can transition to 'pending'
    response = client.put("/api/monitoring/requests/10", json={"status": "pending"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_request_supervisor_can_update_any(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    # Request created by user ID 99 (supervisor with ID 2 can still edit it)
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,
        "title": "Old Title",
        "status": "draft",
    }
    mock_db.execute.return_value = "UPDATE 1"

    # Supervisors can set status to 'signed'
    response = client.put("/api/monitoring/requests/10", json={"status": "signed"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
