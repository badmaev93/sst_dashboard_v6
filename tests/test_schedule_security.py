import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user
import db

client = TestClient(app)

def test_schedule_endpoints_unauthorized():
    for endpoint in [
        "/api/monitoring/schedule/",
        "/api/monitoring/schedule/personnel",
        "/api/monitoring/schedule/today",
        "/api/monitoring/schedule/upcoming",
    ]:
        response = client.get(endpoint)
        assert response.status_code == 401

@pytest.fixture
def mock_db_and_auth():
    # Setup mock user auth dependency override
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "observer1",
        "full_name": "Шпачук Денис Иванович",
        "role": "observer",
        "is_active": True,
    }

    # Store old pool and replace with mock
    old_pool = db.pool
    db.pool = AsyncMock()

    yield db.pool

    # Cleanup
    app.dependency_overrides.clear()
    db.pool = old_pool

def test_get_schedule_no_phone(mock_db_and_auth):
    mock_db = mock_db_and_auth
    mock_db.fetch.return_value = [
        {
            "id": 1,
            "shift_start": "2026-07-20T08:00:00Z",
            "shift_end": "2026-07-20T20:00:00Z",
            "role_on_duty": "Наблюдатель",
            "personnel_id": 10,
            "position": "Наблюдатель",
            "full_name": "Шпачук Денис Иванович",
            "user_role": "observer",
            "station_id": 2,
            "station_code": "VVO",
            "station_name": "Владивосток",
        }
    ]

    response = client.get("/api/monitoring/schedule/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "phone" not in data[0]

def test_get_personnel_no_phone(mock_db_and_auth):
    mock_db = mock_db_and_auth
    mock_db.fetch.return_value = [
        {
            "id": 10,
            "position": "Наблюдатель",
            "station_id": 2,
            "full_name": "Шпачук Денис Иванович",
            "user_role": "observer",
            "station_code": "VVO",
            "station_name": "Владивосток",
        }
    ]

    response = client.get("/api/monitoring/schedule/personnel")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "phone" not in data[0]

def test_get_today_schedule_no_phone(mock_db_and_auth):
    mock_db = mock_db_and_auth
    mock_db.fetch.return_value = [
        {
            "id": 1,
            "shift_start": "2026-07-20T08:00:00Z",
            "shift_end": "2026-07-20T20:00:00Z",
            "role_on_duty": "Наблюдатель",
            "full_name": "Шпачук Денис Иванович",
            "position": "Наблюдатель",
            "station_code": "VVO",
            "station_name": "Владивосток",
        }
    ]

    response = client.get("/api/monitoring/schedule/today")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "phone" not in data[0]

def test_get_upcoming_schedule_no_phone(mock_db_and_auth):
    mock_db = mock_db_and_auth
    mock_db.fetch.return_value = [
        {
            "id": 1,
            "shift_start": "2026-07-20T08:00:00Z",
            "shift_end": "2026-07-20T20:00:00Z",
            "role_on_duty": "Наблюдатель",
            "full_name": "Шпачук Денис Иванович",
            "position": "Наблюдатель",
            "station_code": "VVO",
            "station_name": "Владивосток",
        }
    ]

    response = client.get("/api/monitoring/schedule/upcoming")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "phone" not in data[0]
