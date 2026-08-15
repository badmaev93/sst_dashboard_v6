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

def test_update_task_security(mocker):
    from unittest.mock import AsyncMock
    from auth import get_current_user
    import db

    # Mock user 1 (observer)
    user_observer = {"id": 1, "username": "observer", "role": "observer"}
    # Mock user 2 (supervisor)
    user_supervisor = {"id": 2, "username": "supervisor", "role": "supervisor"}

    # Mock existing task assigned to user 1
    mock_task = {"id": 100, "assigned_to": 1, "title": "Existing task"}

    # Mock db pool fetchrow and execute using AsyncMock
    old_pool = db.pool
    db.pool = AsyncMock()

    try:
        # 1. Non-existent task returns 404
        db.pool.fetchrow.return_value = None
        app.dependency_overrides[get_current_user] = lambda: user_observer

        response = client.put("/api/monitoring/calendar/tasks/999", json={"title": "Updated"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

        # 2. Unauthorized update by another user (user 3) returns 403
        db.pool.fetchrow.return_value = mock_task
        user_other = {"id": 3, "username": "other", "role": "observer"}
        app.dependency_overrides[get_current_user] = lambda: user_other

        response = client.put("/api/monitoring/calendar/tasks/100", json={"title": "Updated"})
        assert response.status_code == 403
        assert response.json()["detail"] == "Not authorized to update this task"

        # 3. Authorized update by assigned user returns 200
        app.dependency_overrides[get_current_user] = lambda: user_observer
        response = client.put("/api/monitoring/calendar/tasks/100", json={"title": "Updated"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}

        # 4. Authorized update by supervisor returns 200
        app.dependency_overrides[get_current_user] = lambda: user_supervisor
        response = client.put("/api/monitoring/calendar/tasks/100", json={"title": "Updated"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    finally:
        app.dependency_overrides.clear()
        db.pool = old_pool
