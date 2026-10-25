from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from auth import get_current_user

client = TestClient(app)

def test_api_gfs_map_png_error():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "username": "observer1",
        "role": "observer",
        "is_active": True,
    }

    with patch("app._get_gfs_png", side_effect=Exception("Test exception")):
        response = client.get("/api/gfs/map/gfs_t/0.png")
        assert response.status_code == 500
        assert response.json() == {"detail": "Test exception"}

    app.dependency_overrides.clear()
