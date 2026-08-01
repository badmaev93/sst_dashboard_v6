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
    payload = {
        "title": "Test Event",
        "description": "Some description",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-25T10:00:00Z",
        "ends_at": "2026-07-25T12:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/1", json=payload)
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


def test_update_event_not_found(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Event does not exist
    mock_db.fetchrow.return_value = None

    payload = {
        "title": "Test Event",
        "description": "Some description",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-25T10:00:00Z",
        "ends_at": "2026-07-25T12:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/999", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_event_not_creator_observer_denied(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Event created by user ID 99 (not the current observer with ID 1)
    mock_db.fetchrow.return_value = {
        "created_by": 99,
    }

    payload = {
        "title": "Test Event",
        "description": "Some description",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-25T10:00:00Z",
        "ends_at": "2026-07-25T12:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/10", json=payload)
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


def test_update_event_creator_observer_allowed(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Event created by user ID 1 (matches current observer with ID 1)
    mock_db.fetchrow.return_value = {
        "created_by": 1,
    }
    mock_db.execute.return_value = "UPDATE 1"

    payload = {
        "title": "New Title",
        "description": "Some description",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-25T10:00:00Z",
        "ends_at": "2026-07-25T12:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/10", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_supervisor_can_update_any(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    # Event created by user ID 99 (not current supervisor with ID 2)
    mock_db.fetchrow.return_value = {
        "created_by": 99,
    }
    mock_db.execute.return_value = "UPDATE 1"

    payload = {
        "title": "New Title",
        "description": "Some description",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-25T10:00:00Z",
        "ends_at": "2026-07-25T12:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/10", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
