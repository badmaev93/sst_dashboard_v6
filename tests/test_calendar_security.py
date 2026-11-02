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

def test_update_event_unauthorized():
    response = client.put("/api/monitoring/calendar/events/1", json={
        "title": "New Title", "event_type": "maintenance", "starts_at": "2026-08-01T00:00:00Z"
    })
    assert response.status_code == 401

def test_delete_event_unauthorized():
    response = client.delete("/api/monitoring/calendar/events/1")
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth_engineer():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 10,
        "username": "engineer1",
        "full_name": "Инженер Сидоров",
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
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 20,
        "username": "supervisor1",
        "full_name": "Начальник Петров",
        "role": "supervisor",
        "is_active": True,
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    app.dependency_overrides.clear()
    db.pool = old_pool


EVENT_PAYLOAD = {
    "title": "New Title",
    "description": "Desc",
    "event_type": "maintenance",
    "station_id": 1,
    "starts_at": "2026-08-01T00:00:00Z",
    "ends_at": "2026-08-01T01:00:00Z",
    "all_day": False,
    "color": "#ff0000",
}

def test_update_event_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/events/999", json=EVENT_PAYLOAD)
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_update_event_not_creator_engineer(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "created_by": 99,  # Created by user 99, but logged in as user 10
        "title": "Old Title",
    }

    response = client.put("/api/monitoring/calendar/events/1", json=EVENT_PAYLOAD)
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_event_creator_engineer_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "created_by": 10,  # Matches logged-in user ID 10
        "title": "Old Title",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/1", json=EVENT_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_create_focus_block_unauthorized():
    response = client.post("/api/monitoring/calendar/focus-blocks", json={
        "title": "Deep Work",
        "start_time": "09:00:00",
        "end_time": "11:00:00"
    })
    assert response.status_code == 401


def test_create_focus_block_invalid_payload(mock_db_and_auth_engineer):
    # Missing required start_time and end_time
    response = client.post("/api/monitoring/calendar/focus-blocks", json={
        "title": "Deep Work"
    })
    assert response.status_code == 422


def test_create_focus_block_valid(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {"id": 42}

    response = client.post("/api/monitoring/calendar/focus-blocks", json={
        "title": "Deep Work",
        "start_time": "09:00:00",
        "end_time": "11:00:00",
        "color": "#10b981",
        "day_of_week": 1,
        "recurring": True
    })
    assert response.status_code == 200
    assert response.json() == {"id": 42}
    mock_db.fetchrow.assert_called_once()


def test_list_tasks_non_supervisor_defaults_to_own(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetch.return_value = [{"id": 1, "title": "My Task", "assigned_to": 10}]

    response = client.get("/api/monitoring/calendar/tasks")
    assert response.status_code == 200
    mock_db.fetch.assert_called_once_with(
        "SELECT * FROM tasks WHERE assigned_to = $1 ORDER BY completed ASC, CASE priority WHEN 'P1' THEN 0 WHEN 'P2' THEN 1 WHEN 'P3' THEN 2 END, created_at DESC",
        10,
    )


def test_list_tasks_non_supervisor_forbidden_other_user(mock_db_and_auth_engineer):
    response = client.get("/api/monitoring/calendar/tasks?user_id=99")
    assert response.status_code == 403
    assert "Not authorized to view other users' tasks" in response.json()["detail"]


def test_list_tasks_supervisor_allowed_any(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetch.return_value = [{"id": 2, "title": "User 99 Task", "assigned_to": 99}]

    response = client.get("/api/monitoring/calendar/tasks?user_id=99")
    assert response.status_code == 200
    mock_db.fetch.assert_called_once_with(
        "SELECT * FROM tasks WHERE assigned_to = $1 ORDER BY completed ASC, CASE priority WHEN 'P1' THEN 0 WHEN 'P2' THEN 1 WHEN 'P3' THEN 2 END, created_at DESC",
        99,
    )


def test_list_focus_blocks_non_supervisor_defaults_to_own(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetch.return_value = [{"id": 1, "title": "My Block", "user_id": 10}]

    response = client.get("/api/monitoring/calendar/focus-blocks")
    assert response.status_code == 200
    # Ensure query was filtered by user_id = 10 (logged in engineer ID)
    mock_db.fetch.assert_called_once_with(
        "SELECT * FROM focus_blocks WHERE user_id = $1 ORDER BY start_time", 10
    )


def test_list_focus_blocks_non_supervisor_forbidden_other_user(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer

    response = client.get("/api/monitoring/calendar/focus-blocks?user_id=99")
    assert response.status_code == 403
    assert "Not authorized to view other users' focus blocks" in response.json()["detail"]


def test_list_focus_blocks_supervisor_allowed_any(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetch.return_value = [{"id": 2, "title": "User 99 Block", "user_id": 99}]

    response = client.get("/api/monitoring/calendar/focus-blocks?user_id=99")
    assert response.status_code == 200
    mock_db.fetch.assert_called_once_with(
        "SELECT * FROM focus_blocks WHERE user_id = $1 ORDER BY start_time", 99
    )


def test_list_tasks_non_supervisor_defaults_to_own(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetch.return_value = [{"id": 1, "title": "My Task", "assigned_to": 10}]

    response = client.get("/api/monitoring/calendar/tasks")
    assert response.status_code == 200
    mock_db.fetch.assert_called_once_with(
        "SELECT * FROM tasks WHERE assigned_to = $1 ORDER BY completed ASC, CASE priority WHEN 'P1' THEN 0 WHEN 'P2' THEN 1 WHEN 'P3' THEN 2 END, created_at DESC",
        10
    )


def test_list_tasks_non_supervisor_forbidden_other_user(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer

    response = client.get("/api/monitoring/calendar/tasks?user_id=99")
    assert response.status_code == 403
    assert "Not authorized to view other users' tasks" in response.json()["detail"]


def test_list_tasks_supervisor_allowed_any(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetch.return_value = [{"id": 2, "title": "User 99 Task", "assigned_to": 99}]

    response = client.get("/api/monitoring/calendar/tasks?user_id=99")
    assert response.status_code == 200
    mock_db.fetch.assert_called_once_with(
        "SELECT * FROM tasks WHERE assigned_to = $1 ORDER BY completed ASC, CASE priority WHEN 'P1' THEN 0 WHEN 'P2' THEN 1 WHEN 'P3' THEN 2 END, created_at DESC",
        99
    )


def test_delete_task_unauthorized():
    response = client.delete("/api/monitoring/calendar/tasks/1")
    assert response.status_code == 401


def test_delete_task_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = None

    response = client.delete("/api/monitoring/calendar/tasks/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_delete_task_unauthorized_user(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "assigned_to": 99,  # Assigned to user 99, logged in as user 10
        "title": "Task 1",
    }

    response = client.delete("/api/monitoring/calendar/tasks/1")
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_delete_task_assigned_user_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "assigned_to": 10,  # Matches logged-in user ID 10
        "title": "Task 1",
    }
    mock_db.execute.return_value = "DELETE 1"

    response = client.delete("/api/monitoring/calendar/tasks/1")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_task_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 1,
        "assigned_to": 99,  # Assigned to user 99, supervisor ID is 20
        "title": "Task 1",
    }
    mock_db.execute.return_value = "DELETE 1"

    response = client.delete("/api/monitoring/calendar/tasks/1")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_event_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = None

    response = client.delete("/api/monitoring/calendar/events/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_delete_event_not_creator_engineer(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "created_by": 99,  # Created by user 99, logged in as 10
        "title": "Old Title",
    }

    response = client.delete("/api/monitoring/calendar/events/1")
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_delete_event_creator_engineer_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "created_by": 10,  # Matches logged-in user ID 10
        "title": "Old Title",
    }
    mock_db.execute.return_value = "DELETE 1"

    response = client.delete("/api/monitoring/calendar/events/1")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_event_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 1,
        "created_by": 99,  # Created by user 99, supervisor ID is 20
        "title": "Old Title",
    }
    mock_db.execute.return_value = "DELETE 1"

    response = client.delete("/api/monitoring/calendar/events/1")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_focus_block_unauthorized():
    response = client.put("/api/monitoring/calendar/focus-blocks/1", json={"title": "New Title"})
    assert response.status_code == 401


def test_delete_focus_block_unauthorized():
    response = client.delete("/api/monitoring/calendar/focus-blocks/1")
    assert response.status_code == 401


FOCUS_BLOCK_PAYLOAD = {"title": "Updated Block", "color": "#123456"}


def test_update_focus_block_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/focus-blocks/999", json=FOCUS_BLOCK_PAYLOAD)
    assert response.status_code == 404
    assert response.json()["detail"] == "Focus block not found"


def test_update_focus_block_not_owner_engineer(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "user_id": 99,  # Owned by user 99, but logged in as user 10
        "title": "Old Block",
    }

    response = client.put("/api/monitoring/calendar/focus-blocks/1", json=FOCUS_BLOCK_PAYLOAD)
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_focus_block_owner_engineer_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "user_id": 10,  # Matches logged-in user ID 10
        "title": "Old Block",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/focus-blocks/1", json=FOCUS_BLOCK_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_focus_block_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = None

    response = client.delete("/api/monitoring/calendar/focus-blocks/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Focus block not found"


def test_delete_focus_block_not_owner_engineer(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "user_id": 99,  # Owned by user 99, but logged in as user 10
        "title": "Old Block",
    }

    response = client.delete("/api/monitoring/calendar/focus-blocks/1")
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_delete_focus_block_owner_engineer_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "user_id": 10,  # Matches logged-in user ID 10
        "title": "Old Block",
    }
    mock_db.execute.return_value = "DELETE 1"

    response = client.delete("/api/monitoring/calendar/focus-blocks/1")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_focus_block_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 1,
        "user_id": 99,  # Owned by user 99, supervisor ID is 20
        "title": "Old Block",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/focus-blocks/1", json=FOCUS_BLOCK_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_focus_block_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 1,
        "user_id": 99,  # Owned by user 99, supervisor ID is 20
        "title": "Old Block",
    }
    mock_db.execute.return_value = "DELETE 1"

    response = client.delete("/api/monitoring/calendar/focus-blocks/1")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_task_unauthorized():
    response = client.put("/api/monitoring/calendar/tasks/1", json={"title": "Updated Task"})
    assert response.status_code == 401


TASK_PAYLOAD = {"title": "Updated Task", "completed": True}


def test_update_task_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = None

    response = client.put("/api/monitoring/calendar/tasks/999", json=TASK_PAYLOAD)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_update_task_unauthorized_user(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "assigned_to": 99,  # Assigned to user 99, but logged in as user 10
        "title": "Old Task",
    }

    response = client.put("/api/monitoring/calendar/tasks/1", json=TASK_PAYLOAD)
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_update_task_assigned_user_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "assigned_to": 10,  # Matches logged-in user ID 10
        "title": "Old Task",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/tasks/1", json=TASK_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_task_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 1,
        "assigned_to": 99,  # Assigned to user 99, supervisor ID is 20
        "title": "Old Task",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/tasks/1", json=TASK_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_update_event_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 1,
        "created_by": 99,  # Created by user 99, supervisor ID is 20
        "title": "Old Title",
    }
    mock_db.execute.return_value = "UPDATE 1"

    response = client.put("/api/monitoring/calendar/events/1", json=EVENT_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
