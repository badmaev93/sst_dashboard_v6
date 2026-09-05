import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user
import db

client = TestClient(app)


def test_get_station_forecast_unauthorized():
    response = client.get("/api/monitoring/forecast/stations/1/forecast")
    assert response.status_code == 401


def test_forecast_history_unauthorized():
    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "testuser",
        "full_name": "Тестовый Пользователь",
        "role": "observer",
        "is_active": True,
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    app.dependency_overrides.clear()
    db.pool = old_pool


def test_get_station_forecast_authenticated(mock_db_and_auth):
    mock_db = mock_db_and_auth
    mock_db.fetchrow.side_effect = [
        # station
        {"id": 1, "code": "ST01", "name": "Станция 1", "lat": 60.0, "lon": 30.0},
        # latest reading for wind/wave
        {"wind_speed": 5.0, "wave_height": 0.5},
    ]
    mock_db.fetch.return_value = []

    with patch("services.prophet_forecast.get_station_forecast_prophet", new=AsyncMock(return_value={"forecast": [5.0]*6})), \
         patch("services.data_generator.fetch_station_reading", new=AsyncMock(return_value={"sst": 5.0})):
        response = client.get("/api/monitoring/forecast/stations/1/forecast")

    assert response.status_code == 200
    data = response.json()
    assert data["station_name"] == "Станция 1"
    assert data["station_code"] == "ST01"


def test_forecast_history_authenticated(mock_db_and_auth):
    mock_db = mock_db_and_auth
    mock_db.fetch.return_value = [
        {
            "id": 101,
            "station_id": 1,
            "forecast_hour": 6,
            "sst": 5.5,
            "actual_sst": 5.4,
        }
    ]

    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 101
