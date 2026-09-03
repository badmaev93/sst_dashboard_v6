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


def test_forecast_history_unauthorized():
    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth_user():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "observer1",
        "full_name": "Наблюдатель Ивановов",
        "role": "observer",
        "is_active": True,
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    app.dependency_overrides.clear()
    db.pool = old_pool


def test_get_station_forecast_authorized_not_found(mock_db_and_auth_user):
    mock_db = mock_db_and_auth_user
    mock_db.fetchrow.return_value = None  # Station not found

    response = client.get("/api/monitoring/forecast/stations/999/forecast")
    assert response.status_code == 404
    assert response.json()["detail"] == "Station not found"


def test_forecast_history_authorized(mock_db_and_auth_user):
    mock_db = mock_db_and_auth_user
    mock_db.fetch.return_value = []

    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 200
    assert response.json() == []
