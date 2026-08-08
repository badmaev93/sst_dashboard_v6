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
    mock_db.fetchrow.return_value = None  # Event doesn't exist

    payload = {
        "title": "Check Station B",
        "description": "Routine check",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-10-10T10:00:00Z",
        "ends_at": "2026-10-10T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }

    response = client.put("/api/monitoring/calendar/events/999", json=payload)
    assert response.status_code == 404
    assert "Event not found" in response.json()["detail"]


def test_update_event_not_creator_observer_denied(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Event created by user 99, but current observer has ID 1
    mock_db.fetchrow.return_value = {
        "id": 50,
        "created_by": 99,
        "title": "Other Event"
    }

    payload = {
        "title": "Trying to edit",
        "description": "Exploit check",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-10-10T10:00:00Z",
        "ends_at": "2026-10-10T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }

    response = client.put("/api/monitoring/calendar/events/50", json=payload)
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_event_creator_observer_allowed(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    # Event created by observer with ID 1
    mock_db.fetchrow.return_value = {
        "id": 50,
        "created_by": 1,
        "title": "My Event"
    }
    mock_db.execute.return_value = "UPDATE 1"

    payload = {
        "title": "Updated Event Title",
        "description": "I can edit this",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-10-10T10:00:00Z",
        "ends_at": "2026-10-10T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }

    response = client.put("/api/monitoring/calendar/events/50", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_supervisor_can_update_any(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    # Event created by user 99, supervisor has ID 2
    mock_db.fetchrow.return_value = {
        "id": 50,
        "created_by": 99,
        "title": "Other Event"
    }
    mock_db.execute.return_value = "UPDATE 1"

    payload = {
        "title": "Supervisor Override",
        "description": "Supervisor power",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-10-10T10:00:00Z",
        "ends_at": "2026-10-10T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }

    response = client.put("/api/monitoring/calendar/events/50", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
