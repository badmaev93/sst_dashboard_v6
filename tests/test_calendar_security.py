from fastapi.testclient import TestClient
from app import app

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

def test_update_event_not_found():
    from auth import get_current_user
    import db
    from unittest.mock import AsyncMock

    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "role": "engineer", "username": "engineer1"}
    db.pool = AsyncMock()
    db.pool.fetchrow.return_value = None

    payload = {
        "title": "Updated Event",
        "description": "desc",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-22T10:00:00Z",
        "ends_at": "2026-07-22T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/999", json=payload)
    app.dependency_overrides.clear()
    assert response.status_code == 404

def test_update_event_unauthorized_non_creator():
    from auth import get_current_user
    import db
    from unittest.mock import AsyncMock

    app.dependency_overrides[get_current_user] = lambda: {"id": 2, "role": "engineer", "username": "engineer2"}
    db.pool = AsyncMock()
    db.pool.fetchrow.return_value = {"id": 10, "created_by": 1, "title": "Original Event"}

    payload = {
        "title": "Updated Event",
        "description": "desc",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-22T10:00:00Z",
        "ends_at": "2026-07-22T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/10", json=payload)
    app.dependency_overrides.clear()
    assert response.status_code == 403

def test_update_event_authorized_creator():
    from auth import get_current_user
    import db
    from unittest.mock import AsyncMock

    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "role": "engineer", "username": "engineer1"}
    db.pool = AsyncMock()
    db.pool.fetchrow.return_value = {"id": 10, "created_by": 1, "title": "Original Event"}

    payload = {
        "title": "Updated Event",
        "description": "desc",
        "event_type": "maintenance",
        "station_id": 1,
        "starts_at": "2026-07-22T10:00:00Z",
        "ends_at": "2026-07-22T11:00:00Z",
        "all_day": False,
        "color": "#ff0000"
    }
    response = client.put("/api/monitoring/calendar/events/10", json=payload)
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"ok": True}
