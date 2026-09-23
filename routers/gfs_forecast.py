"""API прогнозов GFS — тайлы, значения по станциям, метаданные."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

import db
from auth import get_current_user
from services.smb_gfs import get_smb_fetcher, FORECAST_HOURS, LON_MIN, LON_MAX, LAT_MIN, LAT_MAX
from services.gee_gfs import _build_lut  # повторное использование таблицы поиска цветовой палитры
from services.serendipity import correct_gfs_sst, correct_gfs_wind

import numpy as np

logger = logging.getLogger(__name__)

gfs_router = APIRouter(prefix="/api/gfs", tags=["gfs"])


@gfs_router.get("/latest")
async def gfs_latest(user=Depends(get_current_user)):
    f = get_smb_fetcher()
    f.fetch_latest()
    info = f.cycle_info
    return {
        "cycle": f"{info['date']} {info['cycle']}" if info['date'] else None,
        "forecast_hours": FORECAST_HOURS,
        "bounds": [LON_MIN, LAT_MIN, LON_MAX, LAT_MAX],
        "source": info["source"],
    }


@gfs_router.get("/timeline")
async def gfs_timeline(user=Depends(get_current_user)):
    return {"hours": FORECAST_HOURS, "labels": [f"+{h}ч" for h in FORECAST_HOURS]}


@gfs_router.get("/tile/{variable}/{hour}")
async def gfs_tile(variable: str, hour: int,
                   colormap: str = Query("RdYlBu_r"),
                   user=Depends(get_current_user)):
    if hour not in FORECAST_HOURS:
        hour = min(FORECAST_HOURS, key=lambda h: abs(h - hour))

    f = get_smb_fetcher()
    png = _render_tile(f, variable, hour, colormap)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=1800"})


@gfs_router.get("/stations/{hour}")
async def gfs_station_forecast(hour: int, user=Depends(get_current_user)):
    if hour not in FORECAST_HOURS:
        hour = min(FORECAST_HOURS, key=lambda h: abs(h - hour))

    stations = []
    if db.pool:
        rows = await db.pool.fetch("SELECT id, code, name, lat, lon FROM stations")
        stations = [dict(r) for r in rows]

    if not stations:
        return []

    f = get_smb_fetcher()
    now = datetime.now(timezone.utc)
    raw_values = _extract_station_values(f, stations, hour)

    results = []
    for rv in raw_values:
        sst_corr, sst_meta = correct_gfs_sst(rv["code"], now.month, rv["sst"])
        wind_corr, wind_meta = correct_gfs_wind(rv["code"], rv["wind_speed"])
        results.append({
            **rv,
            "sst_corrected": sst_corr,
            "wind_speed_corrected": wind_corr,
            "ai_correction": {
                "sst": sst_meta,
                "wind": wind_meta,
            },
        })
    return results


@gfs_router.get("/station/{station_id}/{hour}")
async def gfs_single_station(station_id: int, hour: int, user=Depends(get_current_user)):
    if hour not in FORECAST_HOURS:
        hour = min(FORECAST_HOURS, key=lambda h: abs(h - hour))

    if not db.pool:
        return {"error": "DB not ready"}

    row = await db.pool.fetchrow(
        "SELECT id, code, name, lat, lon FROM stations WHERE id=$1", station_id)
    if not row:
        return {"error": "Station not found"}

    f = get_smb_fetcher()
    now = datetime.now(timezone.utc)
    vals = _extract_station_values(f, [dict(row)], hour)
    if not vals:
        return {"error": "No data"}

    v = vals[0]
    sst_corr, sst_meta = correct_gfs_sst(v["code"], now.month, v["sst"])
    wind_corr, wind_meta = correct_gfs_wind(v["code"], v["wind_speed"])

    return {
        **v,
        "station_name": row["name"],
        "sst_corrected": sst_corr,
        "wind_speed_corrected": wind_corr,
        "ai_correction": {"sst": sst_meta, "wind": wind_meta},
        "all_hours": {},
    }


# ---------------------------------------------------------------------------
# Вспомогательные функции отрисовки (перенесены из gee_gfs, адаптированы для SMBGFSFetcher)
# ---------------------------------------------------------------------------

def _render_tile(fetcher, variable: str, hour: int, colormap: str) -> bytes:
    from PIL import Image
    import io

    data = fetcher.get_hour(hour)

    if variable == "sst":
        grid = data["sst"]
        vmin, vmax = -2.0, 25.0
    elif variable == "wind":
        grid = np.hypot(data["wind_u"], data["wind_v"])
        vmin, vmax = 0.0, 20.0
        colormap = "viridis"
    elif variable == "pressure":
        du = np.gradient(data["wind_u"], axis=1)
        dv = np.gradient(data["wind_v"], axis=0)
        grid = 1013.25 - (du + dv) * 50
        vmin, vmax = 980.0, 1040.0
        colormap = "RdBu_r"
    else:
        grid = data["sst"]
        vmin, vmax = -2.0, 25.0

    norm = np.clip((grid - vmin) / (vmax - vmin), 0, 1)
    norm = norm[::-1]  # разворот севером вверх

    lut = _build_lut(colormap)
    idx = (norm * 255).astype(np.uint8)
    rgb = lut[idx]
    alpha = np.full(grid.shape, 180, dtype=np.uint8)
    rgba = np.dstack([rgb, alpha])

    img = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _extract_station_values(fetcher, stations: list, hour: int) -> list:
    data = fetcher.get_hour(hour)
    lats = data["lats"]
    lons = data["lons"]
    results = []
    for st in stations:
        lat, lon = float(st["lat"]), float(st["lon"])
        j = int(np.clip(np.searchsorted(lats, lat) - 1, 0, len(lats) - 2))
        i = int(np.clip(np.searchsorted(lons, lon) - 1, 0, len(lons) - 2))

        fj = np.clip((lat - lats[j]) / (lats[j + 1] - lats[j] + 1e-9), 0, 1)
        fi = np.clip((lon - lons[i]) / (lons[i + 1] - lons[i] + 1e-9), 0, 1)

        def _interp(arr):
            return float(
                arr[j, i] * (1 - fj) * (1 - fi) +
                arr[j + 1, i] * fj * (1 - fi) +
                arr[j, i + 1] * (1 - fj) * fi +
                arr[j + 1, i + 1] * fj * fi
            )

        results.append({
            "code": st.get("code", ""),
            "station_id": st.get("id"),
            "lat": lat,
            "lon": lon,
            "sst": round(_interp(data["sst"]), 2),
            "wind_u": round(_interp(data["wind_u"]), 2),
            "wind_v": round(_interp(data["wind_v"]), 2),
            "wind_speed": round(float(np.hypot(
                _interp(data["wind_u"]), _interp(data["wind_v"]))), 2),
            "forecast_hour": hour,
        })
    return results
