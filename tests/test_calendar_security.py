import pytest
from fastapi.testclient import TestClient
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

# --- Security Tests for Event Updates (Authorization / Role checks) ---

def test_update_event_unauthorized():
    # No Auth credentials provided
    response = client.put("/api/monitoring/calendar/events/1", json={
        "title": "New Event", "starts_at": "2026-07-20T10:00:00Z", "ends_at": "2026-07-20T11:00:00Z",
        "event_type": "maintenance", "all_day": False, "description": None, "station_id": None, "color": None
    })
    assert response.status_code == 401

def test_update_event_as_observer_forbidden():
    # User is authenticated but is an observer (unauthorized role)
    def mock_observer():
        return {"id": 1, "username": "observer1", "role": "observer", "is_active": True}

    app.dependency_overrides[get_current_user] = mock_observer
    try:
        response = client.put("/api/monitoring/calendar/events/1", json={
            "title": "Observer Attempt",
            "starts_at": "2026-07-20T10:00:00Z",
            "ends_at": "2026-07-20T11:00:00Z",
            "event_type": "meeting",
            "all_day": False,
            "description": None,
            "station_id": None,
            "color": None
        })
        # Should be forbidden for observer
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()

def test_update_event_as_engineer_allowed(monkeypatch):
    # User is authenticated as an engineer (authorized role)
    # We mock db.pool.execute so it doesn't try to touch the database during test
    executed = []
    class MockPool:
        async def execute(self, *args, **kwargs):
            executed.append(args)
            return "UPDATE 1"

    import db
    monkeypatch.setattr(db, "pool", MockPool())

    def mock_engineer():
        return {"id": 2, "username": "eng1", "role": "engineer", "is_active": True}

    app.dependency_overrides[get_current_user] = mock_engineer
    try:
        response = client.put("/api/monitoring/calendar/events/1", json={
            "title": "Engineer Edit",
            "starts_at": "2026-07-20T10:00:00Z",
            "ends_at": "2026-07-20T11:00:00Z",
            "event_type": "maintenance",
            "all_day": False,
            "description": None,
            "station_id": None,
            "color": None
        })
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert len(executed) == 1
    finally:
        app.dependency_overrides.clear()
