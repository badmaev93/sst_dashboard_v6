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
    response = client.put("/api/monitoring/calendar/events/1", json={})
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


# Payload for PUT requests (must contain all fields without defaults in CalendarEventCreate)
test_event_payload = {
    "title": "New Title",
    "description": "New Description",
    "event_type": "meeting",
    "station_id": None,
    "starts_at": "2026-07-20T09:00:00Z",
    "ends_at": "2026-07-20T10:00:00Z",
    "all_day": False,
    "color": None,
}


def test_update_event_not_found(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Event does not exist in DB
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/events/999", json=test_event_payload)
    assert response.status_code == 404
    assert "Event not found" in response.json()["detail"]


def test_update_event_not_creator_observer(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Event created by user 99, not the current observer (ID 1)
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,
        "title": "Old Title",
    }

    response = client.put("/api/monitoring/calendar/events/10", json=test_event_payload)
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_event_creator_observer_allowed(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Event created by user 1 (current observer is user 1)
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 1,
        "title": "Old Title",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/10", json=test_event_payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_supervisor_can_update_any(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    # Event created by user 99, but supervisor (ID 2) is updating
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,
        "title": "Old Title",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/10", json=test_event_payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
