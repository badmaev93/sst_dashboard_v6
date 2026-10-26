from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import db
from app import app
from auth import get_current_user

client = TestClient(app)


def test_gfs_forecast_unauthorized():
    # Verify unauthenticated requests to GFS endpoints return 401 Unauthorized
    assert client.get("/api/gfs/meta").status_code == 401
    assert client.get("/api/gfs/map/gfs_t/0.png").status_code == 401
    assert client.get("/api/gfs/colorscale/gfs_t").status_code == 401
    assert client.get("/api/gfs/wind/0").status_code == 401
    assert client.get("/api/gfs/latest").status_code == 401
    assert client.get("/api/gfs/timeline").status_code == 401
    assert client.get("/api/gfs/tile/sst/0").status_code == 401
    assert client.get("/api/gfs/stations/0").status_code == 401
    assert client.get("/api/gfs/station/1/0").status_code == 401


@pytest.fixture
def mock_db_and_auth():
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


def test_gfs_forecast_authorized(mock_db_and_auth):
    # Verify timeline endpoint returns 200 for authenticated user
    resp_timeline = client.get("/api/gfs/timeline")
    assert resp_timeline.status_code == 200
    assert "hours" in resp_timeline.json()

    # Verify latest endpoint returns 200 when fetcher is mocked
    mock_fetcher = MagicMock()
    mock_fetcher.cycle_info = {"date": "2026-07-21", "cycle": "00Z", "source": "SMB"}
    with patch("routers.gfs_forecast.get_smb_fetcher", return_value=mock_fetcher):
        resp_latest = client.get("/api/gfs/latest")
        assert resp_latest.status_code == 200
        assert resp_latest.json()["cycle"] == "2026-07-21 00Z"
