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

from unittest.mock import AsyncMock, patch
from auth import get_current_user

def test_update_task_not_found():
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "role": "observer"}
    with patch("db.pool") as mock_pool:
        mock_pool.fetchrow = AsyncMock(return_value=None)
        response = client.put("/api/monitoring/calendar/tasks/999", json={"title": "Updated Title"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"
    app.dependency_overrides.clear()

def test_update_task_forbidden():
    app.dependency_overrides[get_current_user] = lambda: {"id": 10, "role": "observer"}
    with patch("db.pool") as mock_pool:
        mock_pool.fetchrow = AsyncMock(return_value={"id": 1, "assigned_to": 20})
        response = client.put("/api/monitoring/calendar/tasks/1", json={"title": "Updated Title"})
        assert response.status_code == 403
        assert response.json()["detail"] == "Not authorized to update this task"
    app.dependency_overrides.clear()

def test_update_task_authorized_owner():
    app.dependency_overrides[get_current_user] = lambda: {"id": 10, "role": "observer"}
    with patch("db.pool") as mock_pool:
        mock_pool.fetchrow = AsyncMock(return_value={"id": 1, "assigned_to": 10})
        mock_pool.execute = AsyncMock(return_value=None)
        response = client.put("/api/monitoring/calendar/tasks/1", json={"title": "Updated Title"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    app.dependency_overrides.clear()

def test_update_task_authorized_supervisor():
    app.dependency_overrides[get_current_user] = lambda: {"id": 99, "role": "supervisor"}
    with patch("db.pool") as mock_pool:
        mock_pool.fetchrow = AsyncMock(return_value={"id": 1, "assigned_to": 20})
        mock_pool.execute = AsyncMock(return_value=None)
        response = client.put("/api/monitoring/calendar/tasks/1", json={"title": "Updated Title"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    app.dependency_overrides.clear()
