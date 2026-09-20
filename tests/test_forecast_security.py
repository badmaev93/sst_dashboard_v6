import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user
import db

client = TestClient(app)

def test_get_station_forecast_unauthorized():
    response = client.get("/api/monitoring/forecast/stations/1/forecast")
    assert response.status_code == 401

def test_get_forecast_history_unauthorized():
    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 401

@pytest.fixture
def mock_db_and_auth_user():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "observer1",
        "full_name": "Иванов И.И.",
        "role": "observer",
        "is_active": True,
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    app.dependency_overrides.clear()
    db.pool = old_pool

def test_get_station_forecast_authorized(mock_db_and_auth_user):
    mock_db = mock_db_and_auth_user
    mock_db.fetchrow.side_effect = [
        {"id": 1, "code": "TIK", "name": "Тикси", "lat": 71.6, "lon": 128.8},
        {"wind_speed": 5.0, "wave_height": 0.5}
    ]
    mock_db.fetch.side_effect = [
        [{"observed_at": "2026-08-01T00:00:00Z", "sst": 4.5}]
    ]

    response = client.get("/api/monitoring/forecast/stations/1/forecast")
    assert response.status_code == 200
    data = response.json()
    assert data["station_code"] == "TIK"
