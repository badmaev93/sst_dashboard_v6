from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user

client = TestClient(app)

def test_delete_equipment_check_unauthenticated():
    app.dependency_overrides.clear()
    res = client.delete("/api/monitoring/equipment/checks/1")
    assert res.status_code == 401

@patch("db.pool")
def test_delete_equipment_check_not_found(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)

    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "engineer1", "role": "engineer"}
    try:
        res = client.delete("/api/monitoring/equipment/checks/999")
        assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()

@patch("db.pool")
def test_delete_equipment_check_unauthorized(mock_pool):
    # Check owned by user 2, but current user is user 1 (engineer)
    mock_pool.fetchrow = AsyncMock(return_value={"id": 10, "checked_by": 2})

    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "engineer1", "role": "engineer"}
    try:
        res = client.delete("/api/monitoring/equipment/checks/10")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()

@patch("db.pool")
def test_delete_equipment_check_creator_authorized(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value={"id": 10, "checked_by": 1})
    mock_pool.execute = AsyncMock(return_value=None)

    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "engineer1", "role": "engineer"}
    try:
        res = client.delete("/api/monitoring/equipment/checks/10")
        assert res.status_code == 200
        assert res.json() == {"ok": True, "id": 10}
    finally:
        app.dependency_overrides.clear()

@patch("db.pool")
def test_delete_equipment_check_supervisor_authorized(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value={"id": 10, "checked_by": 2})
    mock_pool.execute = AsyncMock(return_value=None)

    app.dependency_overrides[get_current_user] = lambda: {"id": 3, "username": "super1", "role": "supervisor"}
    try:
        res = client.delete("/api/monitoring/equipment/checks/10")
        assert res.status_code == 200
        assert res.json() == {"ok": True, "id": 10}
    finally:
        app.dependency_overrides.clear()
