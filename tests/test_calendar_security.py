import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user
import db

client = TestClient(app)

def test_list_events_unauthorized():
    response = client.get("/api/monitoring/calendar/events")
    assert response.status_code == 401

def test_list_tasks_unauthorized():
    response = client.get("/api/monitoring/calendar/tasks")
    assert response.status_code == 401

def test_list_focus_blocks_unauthorized():
    response = client.get("/api/monitoring/calendar/focus-blocks")
    assert response.status_code == 401

def test_update_event_unauthorized():
    response = client.put("/api/monitoring/calendar/events/1", json={
        "title": "New Title", "event_type": "maintenance", "starts_at": "2026-08-01T00:00:00Z"
    })
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth_engineer():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 10,
        "username": "engineer1",
        "full_name": "Инженер Сидоров",
        "role": "engineer",
        "is_active": True,
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    app.dependency_overrides.clear()
    db.pool = old_pool


@pytest.fixture
def mock_db_and_auth_supervisor():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 20,
        "username": "supervisor1",
        "full_name": "Начальник Петров",
        "role": "supervisor",
        "is_active": True,
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    app.dependency_overrides.clear()
    db.pool = old_pool


EVENT_PAYLOAD = {
    "title": "New Title",
    "description": "Desc",
    "event_type": "maintenance",
    "station_id": 1,
    "starts_at": "2026-08-01T00:00:00Z",
    "ends_at": "2026-08-01T01:00:00Z",
    "all_day": False,
    "color": "#ff0000",
}

def test_update_event_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/events/999", json=EVENT_PAYLOAD)
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_update_event_not_creator_engineer(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "created_by": 99,  # Created by user 99, but logged in as user 10
        "title": "Old Title",
    }

    response = client.put("/api/monitoring/calendar/events/1", json=EVENT_PAYLOAD)
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_event_creator_engineer_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "created_by": 10,  # Matches logged-in user ID 10
        "title": "Old Title",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/1", json=EVENT_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


TASK_PAYLOAD = {"title": "Updated Task", "completed": True}

def test_update_task_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/tasks/999", json=TASK_PAYLOAD)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_update_task_not_assigned_engineer(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 5,
        "assigned_to": 99,  # Assigned to user 99, but logged in as user 10
        "title": "Old Task",
    }

    response = client.put("/api/monitoring/calendar/tasks/5", json=TASK_PAYLOAD)
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_task_assigned_engineer_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 5,
        "assigned_to": 10,  # Matches logged-in user ID 10
        "title": "Old Task",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/tasks/5", json=TASK_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_task_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 5,
        "assigned_to": 99,  # Assigned to user 99, supervisor ID is 20
        "title": "Old Task",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/tasks/5", json=TASK_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 1,
        "created_by": 99,  # Created by user 99, supervisor ID is 20
        "title": "Old Title",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/1", json=EVENT_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
