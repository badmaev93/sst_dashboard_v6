import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user
import db

client = TestClient(app)

def test_forecast_endpoints_unauthorized():
    # Verify that requesting without auth yields 401
    for endpoint in [
        "/api/monitoring/forecast/stations/1/forecast",
        "/api/monitoring/forecast/stations/1/forecast/history",
    ]:
        response = client.get(endpoint)
        assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth():
    # Mock user dependency
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


def test_get_station_forecast_authorized(mock_db_and_auth):
    mock_db = mock_db_and_auth

    # Mock database responses for the forecast logic
    mock_db.fetchrow.return_value = {
        "id": 1,
        "code": "VVO",
        "name": "Владивосток",
        "lat": 43.1,
        "lon": 131.9,
        "wind_speed": 5.0,
        "wave_height": 0.5,
    }
    mock_db.fetch.return_value = [
        {"observed_at": "2026-07-20T08:00:00Z", "sst": 15.0}
    ]

    response = client.get("/api/monitoring/forecast/stations/1/forecast")
    assert response.status_code == 200
    data = response.json()
    assert "station_name" in data
    assert data["station_code"] == "VVO"


def test_forecast_history_authorized(mock_db_and_auth):
    mock_db = mock_db_and_auth

    mock_db.fetch.return_value = [
        {
            "id": 1,
            "station_id": 1,
            "forecast_hour": 6,
            "issued_at": "2026-07-20T08:00:00Z",
            "actual_sst": 15.2,
        }
    ]

    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["forecast_hour"] == 6
