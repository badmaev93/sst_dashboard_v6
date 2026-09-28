from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import db
from app import app
from auth import get_current_user

client = TestClient(app)

def test_list_stations_unauthorized():
    response = client.get("/api/monitoring/stations")
    assert response.status_code == 401

def test_get_station_unauthorized():
    response = client.get("/api/monitoring/stations/1")
    assert response.status_code == 401

def test_get_readings_unauthorized():
    response = client.get("/api/monitoring/stations/1/readings")
    assert response.status_code == 401

def test_latest_readings_unauthorized():
    response = client.get("/api/monitoring/readings/latest")
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "observer1",
        "full_name": "Наблюдатель Игорев",
        "role": "observer",
        "is_active": True,
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    yield db.pool
    app.dependency_overrides.clear()
    db.pool = old_pool


def test_list_stations_authorized(mock_db_and_auth):
    mock_db = mock_db_and_auth
    mock_db.fetch.return_value = [
        {"id": 1, "code": "ST01", "name": "Станция 1", "sst": 12.5}
    ]

    response = client.get("/api/monitoring/stations")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["code"] == "ST01"


def test_get_station_authorized(mock_db_and_auth):
    mock_db = mock_db_and_auth
    mock_db.fetchrow.return_value = {"id": 1, "code": "ST01", "name": "Станция 1"}
    mock_db.fetch.return_value = [{"id": 10, "station_id": 1, "sst": 12.5}]

    response = client.get("/api/monitoring/stations/1")
    assert response.status_code == 200
    res = response.json()
    assert res["station"]["code"] == "ST01"
    assert len(res["readings"]) == 1
