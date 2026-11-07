import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user
import db

client = TestClient(app)


def test_create_assignment_unauthorized():
    # Calling POST /api/monitoring/schedule/ without auth should return 401
    res = client.post("/api/monitoring/schedule/", json={
        "personnel_id": 1,
        "station_id": 2,
        "shift_start": "2026-07-20T08:00:00Z",
        "shift_end": "2026-07-20T20:00:00Z",
    })
    assert res.status_code == 401

    # Calling POST /api/monitoring/users/assignments without auth should return 401
    res = client.post("/api/monitoring/users/assignments", json={
        "personnel_id": 1,
        "station_id": 2,
        "shift_start": "2026-07-20T08:00:00Z",
        "shift_end": "2026-07-20T20:00:00Z",
    })
    assert res.status_code == 401


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


def test_create_assignment_forbidden_for_non_supervisor(mock_db_and_auth_observer):
    res = client.post("/api/monitoring/schedule/", json={
        "personnel_id": 1,
        "station_id": 2,
        "shift_start": "2026-07-20T08:00:00Z",
        "shift_end": "2026-07-20T20:00:00Z",
    })
    assert res.status_code == 403

    res = client.post("/api/monitoring/users/assignments", json={
        "personnel_id": 1,
        "station_id": 2,
        "shift_start": "2026-07-20T08:00:00Z",
        "shift_end": "2026-07-20T20:00:00Z",
    })
    assert res.status_code == 403


def test_create_assignment_validation_missing_fields(mock_db_and_auth_supervisor):
    # Missing required fields like personnel_id, shift_start, etc. should return 422
    res = client.post("/api/monitoring/schedule/", json={})
    assert res.status_code == 422

    res = client.post("/api/monitoring/users/assignments", json={})
    assert res.status_code == 422


def test_create_assignment_validation_invalid_types(mock_db_and_auth_supervisor):
    # Invalid types (e.g. non-integer ID or invalid date format) should return 422
    res = client.post("/api/monitoring/schedule/", json={
        "personnel_id": "not-an-int",
        "station_id": 2,
        "shift_start": "invalid-datetime",
        "shift_end": "2026-07-20T20:00:00Z",
    })
    assert res.status_code == 422

    res = client.post("/api/monitoring/users/assignments", json={
        "personnel_id": 1,
        "station_id": "not-an-int",
        "shift_start": "2026-07-20T08:00:00Z",
        "shift_end": "not-a-datetime",
    })
    assert res.status_code == 422


def test_create_assignment_success_schedule(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {"id": 42}

    payload = {
        "personnel_id": 1,
        "station_id": 2,
        "shift_start": "2026-07-20T08:00:00Z",
        "shift_end": "2026-07-20T20:00:00Z",
        "role_on_duty": "Инженер-метеоролог",
    }
    res = client.post("/api/monitoring/schedule/", json=payload)
    assert res.status_code == 200
    assert res.json() == {"id": 42}
    assert mock_db.fetchrow.called


def test_create_assignment_success_users(mock_db_and_auth_supervisor):
    mock_db = mock_db_and_auth_supervisor
    mock_db.fetchrow.return_value = {"id": 43}

    payload = {
        "personnel_id": 1,
        "station_id": 2,
        "shift_start": "2026-07-20T08:00:00Z",
        "shift_end": "2026-07-20T20:00:00Z",
    }
    res = client.post("/api/monitoring/users/assignments", json=payload)
    assert res.status_code == 200
    assert res.json() == {"id": 43}
    assert mock_db.fetchrow.called
