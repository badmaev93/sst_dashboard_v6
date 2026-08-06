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
        "title": "New", "description": "New", "event_type": "maintenance",
        "station_id": 1, "starts_at": "2026-07-20T08:00:00", "ends_at": "2026-07-20T09:00:00",
        "all_day": False, "color": "#000000"
    })
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth_observer():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "observer1",
        "full_name": "Observer",
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
        "full_name": "Supervisor",
        "role": "supervisor",
        "is_active": True,
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    app.dependency_overrides.clear()
    db.pool = old_pool


def test_update_event_missing(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/events/999", json={
        "title": "New", "description": "New", "event_type": "maintenance",
        "station_id": 1, "starts_at": "2026-07-20T08:00:00", "ends_at": "2026-07-20T09:00:00",
        "all_day": False, "color": "#000000"
    })
    assert response.status_code == 404
    assert "Calendar event not found" in response.json()["detail"]


def test_update_event_unauthorized_non_creator(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,
        "title": "Old Title"
    }

    response = client.put("/api/monitoring/calendar/events/10", json={
        "title": "New", "description": "New", "event_type": "maintenance",
        "station_id": 1, "starts_at": "2026-07-20T08:00:00", "ends_at": "2026-07-20T09:00:00",
        "all_day": False, "color": "#000000"
    })
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_event_creator_allowed(mock_db_and_auth_observer):
    mock_db = mock_db_and_auth_observer
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 1,
        "title": "Old Title"
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/10", json={
        "title": "New", "description": "New", "event_type": "maintenance",
        "station_id": 1, "starts_at": "2026-07-20T08:00:00", "ends_at": "2026-07-20T09:00:00",
        "all_day": False, "color": "#000000"
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 10,
        "created_by": 99,
        "title": "Old Title"
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/10", json={
        "title": "New", "description": "New", "event_type": "maintenance",
        "station_id": 1, "starts_at": "2026-07-20T08:00:00", "ends_at": "2026-07-20T09:00:00",
        "all_day": False, "color": "#000000"
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True}
