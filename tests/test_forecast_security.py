from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_get_forecast_unauthorized():
    response = client.get("/api/monitoring/forecast/stations/1/forecast")
    assert response.status_code == 401

def test_get_forecast_history_unauthorized():
    response = client.get("/api/monitoring/forecast/stations/1/forecast/history")
    assert response.status_code == 401
