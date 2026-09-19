from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import db
from app import app
from auth import get_current_user

client = TestClient(app)


def test_stations_unauthorized():
    # Verify that requesting station endpoints without auth yields 401
    response = client.get("/api/monitoring/stations")
    assert response.status_code == 401

    response = client.get("/api/monitoring/stations/1")
    assert response.status_code == 401

    response = client.get("/api/monitoring/stations/1/readings")
    assert response.status_code == 401

    response = client.get("/api/monitoring/readings/latest")
    assert response.status_code == 401


@pytest.fixture
def mock_db_and_auth_user():
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


def test_stations_authorized(mock_db_and_auth_user):
    mock_db = mock_db_and_auth_user
    mock_db.fetch.return_value = [
        {"id": 1, "code": "ST01", "name": "Station 1", "sst": 10.5}
    ]
    mock_db.fetchrow.return_value = {
        "id": 1,
        "code": "ST01",
        "name": "Station 1",
        "lat": 45.0,
        "lon": 140.0,
    }

    response = client.get("/api/monitoring/stations")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["code"] == "ST01"

    response = client.get("/api/monitoring/stations/1")
    assert response.status_code == 200
    assert response.json()["station"]["code"] == "ST01"

    response = client.get("/api/monitoring/stations/1/readings")
    assert response.status_code == 200

    response = client.get("/api/monitoring/readings/latest")
    assert response.status_code == 200
