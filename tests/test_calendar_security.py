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

    # PUT requests without auth should return 401
    response = client.put("/api/monitoring/calendar/events/1", json={
        "title": "Unauth Test",
        "event_type": "maintenance",
        "starts_at": "2026-07-20T10:00:00Z",
        "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False,
        "station_id": None,
        "description": None,
        "color": None
    })
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth_engineer():
    # User ID 5: engineer role (not a supervisor)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 5,
        "username": "engineer1",
        "full_name": "Тестовый Инженер",
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
    # User ID 6: supervisor role
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 6,
        "username": "supervisor1",
        "full_name": "Тестовый Супервизор",
        "role": "supervisor",
        "is_active": True,
    }

    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool

    app.dependency_overrides.clear()
    db.pool = old_pool


def test_update_event_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    # Mock return value to signify event not found
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/events/999", json={
        "title": "Non-existent",
        "event_type": "maintenance",
        "starts_at": "2026-07-20T10:00:00Z",
        "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False,
        "station_id": None,
        "description": None,
        "color": None
    })
    assert response.status_code == 404
    assert "Event not found" in response.json()["detail"]


def test_update_event_unauthorized_non_creator_non_supervisor(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    # Event created by User 99 (engineer with ID 5 is NOT authorized)
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,
        "title": "Old Event Title",
    }

    response = client.put("/api/monitoring/calendar/events/10", json={
        "title": "New Event Title",
        "event_type": "maintenance",
        "starts_at": "2026-07-20T10:00:00Z",
        "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False,
        "station_id": None,
        "description": None,
        "color": None
    })
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_event_creator_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    # Event created by User 5 (matches engineer with ID 5)
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 5,
        "title": "Old Event Title",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/10", json={
        "title": "New Event Title",
        "event_type": "maintenance",
        "starts_at": "2026-07-20T10:00:00Z",
        "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False,
        "station_id": None,
        "description": None,
        "color": None
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    # Event created by User 99 (supervisor with ID 6 is still allowed)
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,
        "title": "Old Event Title",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/10", json={
        "title": "Supervisor Override",
        "event_type": "maintenance",
        "starts_at": "2026-07-20T10:00:00Z",
        "ends_at": "2026-07-20T11:00:00Z",
        "all_day": False,
        "station_id": None,
        "description": None,
        "color": None
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True}

def test_list_tasks_unauthorized():
    response = client.get("/api/monitoring/calendar/tasks")
    assert response.status_code == 401

def test_list_focus_blocks_unauthorized():
    response = client.get("/api/monitoring/calendar/focus-blocks")
    assert response.status_code == 401
