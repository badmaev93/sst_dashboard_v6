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
        "title": "Test", "description": "Test", "event_type": "inspection",
        "station_id": 1, "starts_at": "2026-07-20T10:00:00Z", "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False, "color": "#ff0000"
    })
    assert response.status_code == 401

def test_update_task_unauthorized():
    response = client.put("/api/monitoring/calendar/tasks/1", json={"title": "Test"})
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth_observer():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 10,
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
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 99,
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


# --- Event security tests ---

def test_update_event_not_found(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = None

    payload = {
        "title": "New Title", "description": "Desc", "event_type": "inspection",
        "station_id": 1, "starts_at": "2026-07-20T10:00:00Z", "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False, "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/999", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_update_event_forbidden_non_creator(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = {
        "id": 1, "created_by": 55, "title": "Old Title"
    }

    payload = {
        "title": "New Title", "description": "Desc", "event_type": "inspection",
        "station_id": 1, "starts_at": "2026-07-20T10:00:00Z", "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False, "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/1", json=payload)
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_event_allowed_creator(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = {
        "id": 1, "created_by": 10, "title": "Old Title"
    }
    mock_db.execute.return_value = "UPDATE 1"

    payload = {
        "title": "New Title", "description": "Desc", "event_type": "inspection",
        "station_id": 1, "starts_at": "2026-07-20T10:00:00Z", "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False, "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/1", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_allowed_supervisor(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 1, "created_by": 55, "title": "Old Title"
    }
    mock_db.execute.return_value = "UPDATE 1"

    payload = {
        "title": "New Title", "description": "Desc", "event_type": "inspection",
        "station_id": 1, "starts_at": "2026-07-20T10:00:00Z", "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False, "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/1", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


# --- Task security tests ---

def test_update_task_not_found(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/tasks/999", json={"title": "New Task Title"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_update_task_forbidden_non_assignee(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = {
        "id": 5, "assigned_to": 55, "title": "Old Task"
    }

    response = client.put("/api/monitoring/calendar/tasks/5", json={"title": "New Task Title"})
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_task_allowed_assignee(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = {
        "id": 5, "assigned_to": 10, "title": "Old Task"
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/tasks/5", json={"title": "New Task Title"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_task_allowed_supervisor(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 5, "assigned_to": 55, "title": "Old Task"
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/tasks/5", json={"title": "New Task Title"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
