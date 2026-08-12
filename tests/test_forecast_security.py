import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user
import db

client = TestClient(app)

def test_forecast_endpoints_unauthorized():
    # Verify that requesting without auth yields 401
    response = client.get("/api/monitoring/forecast/stations/1/forecast")
    assert response.status_code == 401

    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth():
    # Setup dependency override for mock user
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "observer1",
        "full_name": "Шпачук Денис Иванович",
        "role": "observer",
        "is_active": True,
    }

    # Save original pool and swap with mock
    old_pool = db.pool
    db.pool = AsyncMock()

    yield db.pool

    # Cleanup
    app.dependency_overrides.clear()
    db.pool = old_pool


def test_get_forecast_authorized(mock_db_and_auth):
    mock_db = mock_db_and_auth
    # Mock database responses
    async def mock_fetchrow(query, *args):
        if "stations" in query:
            return {
                "id": 1,
                "code": "VVO",
                "name": "Владивосток",
                "lat": 43.1,
                "lon": 131.9,
            }
        elif "readings" in query:
            return {
                "wind_speed": 6.2,
                "wave_height": 1.1,
            }
        return None

    mock_db.fetchrow.side_effect = mock_fetchrow
    mock_db.fetch.return_value = [] # no past readings

    response = client.get("/api/monitoring/forecast/stations/1/forecast")
    assert response.status_code == 200
    data = response.json()
    assert data["station_name"] == "Владивосток"
    assert data["station_code"] == "VVO"


def test_forecast_history_authorized(mock_db_and_auth):
    mock_db = mock_db_and_auth
    mock_db.fetch.return_value = [
        {
            "id": 1,
            "station_id": 1,
            "forecast_hour": 6,
            "sst": 12.5,
            "actual_sst": 12.3,
            "issued_at": "2026-07-20T00:00:00Z"
        }
    ]

    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["forecast_hour"] == 6
