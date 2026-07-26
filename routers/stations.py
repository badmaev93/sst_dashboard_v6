from fastapi import APIRouter, HTTPException, Depends, Query
import db
from auth import get_current_user, require_role

stations_router = APIRouter(prefix="/api/monitoring", tags=["stations"])

@stations_router.get("/stations")
async def list_stations():
    rows = await db.pool.fetch("""
        SELECT s.*, r.sst, r.temp_air, r.wind_speed, r.wave_height, r.pressure,
               r.visibility, r.humidity, r.observed_at as last_reading_at, r.status as reading_status
        FROM stations s
        LEFT JOIN LATERAL (
            SELECT * FROM readings WHERE station_id = s.id ORDER BY observed_at DESC LIMIT 1
        ) r ON true
        ORDER BY s.id
    """)
    return [dict(r) for r in rows]

@stations_router.get("/stations/{station_id}")
async def get_station(station_id: int):
    station = await db.pool.fetchrow("SELECT * FROM stations WHERE id = $1", station_id)
    if not station:
        raise HTTPException(404, "Station not found")
    readings = await db.pool.fetch(
        "SELECT * FROM readings WHERE station_id = $1 AND observed_at > now() - interval '24 hours' ORDER BY observed_at",
        station_id)
    return {"station": dict(station), "readings": [dict(r) for r in readings]}

@stations_router.get("/stations/{station_id}/readings")
async def get_readings(station_id: int, hours: int = Query(24, ge=1, le=720)):
    rows = await db.pool.fetch(
        "SELECT * FROM readings WHERE station_id = $1 AND observed_at > now() - make_interval(hours => $2) ORDER BY observed_at",
        station_id, hours)
    return [dict(r) for r in rows]

@stations_router.get("/readings/latest")
async def latest_readings():
    rows = await db.pool.fetch("""
        SELECT DISTINCT ON (s.id) s.id, s.code, s.name, s.lat, s.lon, s.region, s.status,
               r.sst, r.temp_air, r.wind_speed, r.wind_dir, r.wave_height, r.pressure,
               r.visibility, r.observed_at
        FROM stations s
        LEFT JOIN readings r ON r.station_id = s.id
        ORDER BY s.id, r.observed_at DESC
    """)
    return [dict(r) for r in rows]

@stations_router.post("/readings")
async def create_reading(data: dict, user=Depends(require_role("observer", "supervisor"))):
    # Добавление измерения
    row = await db.pool.fetchrow("""
        INSERT INTO readings (station_id, observed_at, sst, temp_air, wave_height, wave_period,
            wind_speed, wind_dir, pressure, visibility, humidity, status)
        VALUES ($1, now(), $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id
    """, data["station_id"], data.get("sst"), data.get("temp_air"), data.get("wave_height"),
        data.get("wave_period"), data.get("wind_speed"), data.get("wind_dir"),
        data.get("pressure"), data.get("visibility"), data.get("humidity"), data.get("status", "normal"))
    return {"id": row["id"]}
