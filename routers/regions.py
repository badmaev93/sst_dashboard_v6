from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
import db
import json
import os
from auth import get_current_user

regions_router = APIRouter(prefix="/api/regions", tags=["regions"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
GEOJSON_PATH = os.path.join(DATA_DIR, "regions.geojson")


def _load_geojson():
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _compute_bbox(geom):
    """Вычисляет [lon_min, lat_min, lon_max, lat_max] из геометрии GeoJSON."""
    coords_list = []
    geom_type = geom.get("type", "")
    raw_coords = geom.get("coordinates", [])

    if geom_type == "Polygon":
        for ring in raw_coords:
            coords_list.extend(ring)
    elif geom_type == "MultiPolygon":
        for polygon in raw_coords:
            for ring in polygon:
                coords_list.extend(ring)
    else:
        return None

    if not coords_list:
        return None

    lons = [c[0] for c in coords_list]
    lats = [c[1] for c in coords_list]
    return [min(lons), min(lats), max(lons), max(lats)]


@regions_router.get("/")
async def list_regions(user=Depends(get_current_user)):
    geo = _load_geojson()
    regions = []
    for feat in geo["features"]:
        props = feat["properties"]
        code = props["code"]
        station_codes = props["stations"]

        # Вычисление bbox из геометрии
        geom = feat.get("geometry", {})
        bbox = _compute_bbox(geom)

        station_count = 0
        avg_sst = None
        active_alerts = 0
        statuses = {"normal": 0, "warning": 0, "critical": 0, "offline": 0}

        if db.pool and station_codes:
            rows = await db.pool.fetch("""
                SELECT s.id, s.code, s.name, s.status,
                       r.sst, r.observed_at
                FROM stations s
                LEFT JOIN LATERAL (
                    SELECT sst, observed_at FROM readings
                    WHERE station_id = s.id ORDER BY observed_at DESC LIMIT 1
                ) r ON true
                WHERE s.code = ANY($1)
            """, station_codes)

            station_count = len(rows)
            sst_vals = [r["sst"] for r in rows if r["sst"] is not None]
            if sst_vals:
                avg_sst = round(sum(sst_vals) / len(sst_vals), 2)

            for r in rows:
                st = r["status"] or "normal"
                if st in statuses:
                    statuses[st] += 1
                if st in ("warning", "critical"):
                    active_alerts += 1

        region_data = {
            "code": code,
            "name": props["name"],
            "color": props["color"],
            "station_codes": station_codes,
            "station_count": station_count,
            "avg_sst": avg_sst,
            "active_alerts": active_alerts,
            "statuses": statuses,
        }
        if bbox:
            region_data["bbox"] = bbox
            region_data["center_lat"] = (bbox[1] + bbox[3]) / 2
            region_data["center_lon"] = (bbox[0] + bbox[2]) / 2

        regions.append(region_data)

    return regions


@regions_router.get("/geojson")
async def get_geojson(user=Depends(get_current_user)):
    if not os.path.exists(GEOJSON_PATH):
        raise HTTPException(404, "GeoJSON file not found")
    return FileResponse(GEOJSON_PATH, media_type="application/geo+json")


@regions_router.get("/{code}")
async def get_region(code: str, user=Depends(get_current_user)):
    code = code.upper()
    geo = _load_geojson()

    region_props = None
    for feat in geo["features"]:
        if feat["properties"]["code"] == code:
            region_props = feat["properties"]
            break

    if not region_props:
        raise HTTPException(404, f"Region {code} not found")

    station_codes = region_props["stations"]
    stations = []

    if db.pool and station_codes:
        rows = await db.pool.fetch("""
            SELECT s.id, s.code, s.name, s.lat, s.lon, s.region, s.status,
                   r.sst, r.temp_air, r.wind_speed, r.wave_height,
                   r.pressure, r.observed_at
            FROM stations s
            LEFT JOIN LATERAL (
                SELECT sst, temp_air, wind_speed, wave_height, pressure, observed_at
                FROM readings WHERE station_id = s.id
                ORDER BY observed_at DESC LIMIT 1
            ) r ON true
            WHERE s.code = ANY($1)
            ORDER BY s.name
        """, station_codes)
        stations = [dict(r) for r in rows]

    sst_vals = [s["sst"] for s in stations if s.get("sst") is not None]
    avg_sst = round(sum(sst_vals) / len(sst_vals), 2) if sst_vals else None
    active_alerts = sum(1 for s in stations if s.get("status") in ("warning", "critical"))

    return {
        "code": code,
        "name": region_props["name"],
        "color": region_props["color"],
        "station_count": len(stations),
        "avg_sst": avg_sst,
        "active_alerts": active_alerts,
        "stations": stations,
    }
