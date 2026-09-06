import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user
import db

client = TestClient(app)

def test_forecast_unauthorized():
    response = client.get("/api/monitoring/forecast/stations/1/forecast")
    assert response.status_code == 401

    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth_user():
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


def test_forecast_authorized(mock_db_and_auth_user):
    mock_db = mock_db_and_auth_user
    mock_db.fetchrow.side_effect = [
        {"id": 1, "code": "ST01", "name": "Станция 1", "lat": 43.0, "lon": 131.0},  # station
        {"wind_speed": 5.0, "wave_height": 0.5},  # latest reading
    ]
    mock_db.fetch.return_value = []

    with patch("services.data_generator.fetch_station_reading", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"sst": 10.0}
        response = client.get("/api/monitoring/forecast/stations/1/forecast")
        assert response.status_code == 200
        data = response.json()
        assert data["station_code"] == "ST01"


def test_forecast_history_authorized(mock_db_and_auth_user):
    mock_db = mock_db_and_auth_user
    mock_db.fetch.return_value = [
        {"id": 100, "station_id": 1, "forecast_hour": 6, "actual_sst": 10.5}
    ]

    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 100
