from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import db
from app import app
from auth import get_current_user

client = TestClient(app)


def test_equipment_checks_unauthorized():
    response = client.get("/api/monitoring/equipment/checks")
    assert response.status_code == 401

    response = client.post("/api/monitoring/equipment/checks", json={})
    assert response.status_code == 401

    response = client.delete("/api/monitoring/equipment/checks/1")
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


def test_delete_check_not_found(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = None

    response = client.delete("/api/monitoring/equipment/checks/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Equipment check not found"


def test_delete_check_unauthorized_user(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "checked_by": 99,  # Check created by user 99, but engineer ID is 10
        "equipment": "Sensor",
    }

    response = client.delete("/api/monitoring/equipment/checks/1")
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


def test_delete_check_creator_engineer_allowed(mock_db_and_auth_engineer):
    mock_db = mock_db_and_auth_engineer
    mock_db.fetchrow.return_value = {
        "id": 1,
        "checked_by": 10,  # Matches engineer ID 10
        "equipment": "Sensor",
    }
    mock_db.execute.return_value = "DELETE 1"

    response = client.delete("/api/monitoring/equipment/checks/1")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_check_supervisor_allowed(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {
        "id": 1,
        "checked_by": 99,  # Check created by user 99, supervisor ID is 20
        "equipment": "Sensor",
    }
    mock_db.execute.return_value = "DELETE 1"

    response = client.delete("/api/monitoring/equipment/checks/1")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
