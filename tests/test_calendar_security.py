from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import db
from app import app
from auth import get_current_user

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
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/events/999", json={
        "title": "New Event",
        "description": "Some description",
        "event_type": "meeting",
        "station_id": None,
        "starts_at": "2026-07-25T10:00:00Z",
        "ends_at": "2026-07-25T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    })
    assert response.status_code == 404
    assert "Calendar event not found" in response.json()["detail"]


def test_update_event_not_creator_observer(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,  # different from current user id = 1
        "title": "Old Event"
    }

    response = client.put("/api/monitoring/calendar/events/10", json={
        "title": "New Event",
        "description": "Some description",
        "event_type": "meeting",
        "station_id": None,
        "starts_at": "2026-07-25T10:00:00Z",
        "ends_at": "2026-07-25T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    })
    assert response.status_code == 403
    assert "Not authorized to update this calendar event" in response.json()["detail"]


def test_update_event_creator_observer_allowed(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 1,  # same as current user id = 1
        "title": "Old Event"
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/10", json={
        "title": "New Event",
        "description": "Some description",
        "event_type": "meeting",
        "station_id": None,
        "starts_at": "2026-07-25T10:00:00Z",
        "ends_at": "2026-07-25T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_supervisor_can_update_any(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,  # supervisor (id = 2) can edit anyone's event
        "title": "Old Event"
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/10", json={
        "title": "New Event",
        "description": "Some description",
        "event_type": "meeting",
        "station_id": None,
        "starts_at": "2026-07-25T10:00:00Z",
        "ends_at": "2026-07-25T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True}
