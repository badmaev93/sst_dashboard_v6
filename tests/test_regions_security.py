from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import db
from app import app
from auth import get_current_user

client = TestClient(app)

def test_regions_endpoints_unauthorized():
    for endpoint in [
        "/api/regions/",
        "/api/regions/geojson",
        "/api/regions/OKH",
    ]:
        response = client.get(endpoint)
        assert response.status_code == 401

@pytest.fixture
def mock_db_and_auth(tmp_path, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "testuser",
        "role": "observer"
    }
    old_pool = db.pool
    db.pool = AsyncMock()
    db.pool.fetch = AsyncMock(return_value=[])

    # Create dummy geojson file to avoid FileNotFoundError in test environment
    import routers.regions as regions_module
    dummy_geojson = tmp_path / "regions.geojson"
    dummy_geojson.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    monkeypatch.setattr(regions_module, "GEOJSON_PATH", str(dummy_geojson))

    yield
    app.dependency_overrides.clear()
    db.pool = old_pool

def test_regions_endpoints_authorized(mock_db_and_auth):
    res_list = client.get("/api/regions/")
    assert res_list.status_code == 200

    res_geojson = client.get("/api/regions/geojson")
    assert res_geojson.status_code == 200
