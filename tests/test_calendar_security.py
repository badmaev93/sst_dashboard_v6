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


@pytest.fixture
def mock_db_and_auth_engineer():
    # User 3: engineer role (not a supervisor)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 3,
        "username": "engineer1",
        "full_name": "Петров Петр Петрович",
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
    # User 4: supervisor role
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 4,
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


def test_update_event_missing(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    # Event does not exist in the database
    mock_db.fetchrow.return_value = None

    payload = {
        "title": "New Event",
        "description": "Some description",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-22T10:00:00+00:00",
        "ends_at": "2026-07-22T12:00:00+00:00",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/999", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_event_not_creator_engineer_denied(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    # Event created by user ID 99 (not the current engineer with ID 3)
    mock_db.fetchrow.return_value = {
        "id": 5,
        "created_by": 99,
        "title": "Old Event",
    }

    payload = {
        "title": "New Event",
        "description": "Some description",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-22T10:00:00+00:00",
        "ends_at": "2026-07-22T12:00:00+00:00",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/5", json=payload)
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_event_creator_engineer_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    # Event created by user ID 3 (matches current engineer with ID 3)
    mock_db.fetchrow.return_value = {
        "id": 5,
        "created_by": 3,
        "title": "Old Event",
    }
    mock_db.execute.return_value = "UPDATE 1"

    payload = {
        "title": "New Event",
        "description": "Some description",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-22T10:00:00+00:00",
        "ends_at": "2026-07-22T12:00:00+00:00",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/5", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    # Event created by user ID 99 (supervisor can edit any event)
    mock_db.fetchrow.return_value = {
        "id": 5,
        "created_by": 99,
        "title": "Old Event",
    }
    mock_db.execute.return_value = "UPDATE 1"

    payload = {
        "title": "New Event",
        "description": "Some description",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-22T10:00:00+00:00",
        "ends_at": "2026-07-22T12:00:00+00:00",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/5", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
