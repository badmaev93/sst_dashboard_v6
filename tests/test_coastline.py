from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import app

client = TestClient(app.app)

@pytest.fixture(autouse=True)
def clear_cache():
    app._coastline_cache.clear()
    yield
    app._coastline_cache.clear()

def test_api_coastline_geojson_not_found():
    with patch("app._load_coast_geojson", return_value=None):
        response = client.get("/api/coastline.geojson")
        assert response.status_code == 404
        assert response.json() == {"detail": "ne_10m_land.geojson not found"}

def test_api_coastline_geojson_success():
    mock_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    # valid polygon in BOX_W
                    "coordinates": [[[150.0, 50.0], [151.0, 50.0], [151.0, 51.0], [150.0, 51.0], [150.0, 50.0]]]
                },
                "properties": {}
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    # valid polygon in BOX_E
                    "coordinates": [[[-170.0, 50.0], [-169.0, 50.0], [-169.0, 51.0], [-170.0, 51.0], [-170.0, 50.0]]]
                },
                "properties": {}
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    # invalid polygon (bowtie) in BOX_W
                    "coordinates": [[[160.0, 50.0], [161.0, 51.0], [161.0, 50.0], [160.0, 51.0], [160.0, 50.0]]]
                },
                "properties": {}
            }
        ]
    }

    with patch("app._load_coast_geojson", return_value=mock_geojson) as mock_load:
        response = client.get("/api/coastline.geojson")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/geo+json"

        data = response.json()
        assert data["type"] == "FeatureCollection"
        # We expect 3 features (one for the first, one for the second, and make_valid on the third might yield multi parts but since they are in BOX_W, it will be added as one geometry)
        assert len(data["features"]) >= 3

        halves = [feat["properties"]["half"] for feat in data["features"]]
        assert "west" in halves
        assert "east" in halves

        # Verify caching works
        assert "geojson" in app._coastline_cache

        # Second call should use cache
        mock_load.reset_mock()
        response2 = client.get("/api/coastline.geojson")
        assert response2.status_code == 200
        mock_load.assert_not_called()

        assert response2.json() == data
