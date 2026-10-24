import asyncio
import time
import db
import random
from datetime import datetime, timezone, timedelta

async def setup_data():
    await db.init_db()

    # insert 50 stations
    stations = []
    for i in range(50):
        code = f"ST{i:03}"
        name = f"Station {i}"
        row = await db.pool.fetchrow(
            "INSERT INTO stations (code, name, lat, lon) VALUES ($1, $2, $3, $4) RETURNING id",
            code, name, 0.0, 0.0
        )
        stations.append(row["id"])

    # insert 100 readings for each
    now = datetime.now(timezone.utc)
    for st_id in stations:
        for i in range(100):
            obs_time = now - timedelta(hours=i)
            await db.pool.execute(
                "INSERT INTO readings (station_id, observed_at, sst) VALUES ($1, $2, $3)",
                st_id, obs_time, 20.0 + random.random()
            )

async def run_baseline():
    await db.init_db()

    start_time = time.time()

    stations = await db.pool.fetch("SELECT id, code, name FROM stations ORDER BY id")
    print(f"Got {len(stations)} stations")

    total_readings = 0
    readings_dict = {}
    for st in stations:
        readings = await db.pool.fetch(
            "SELECT observed_at, sst FROM readings "
            "WHERE station_id = $1 AND sst IS NOT NULL "
            "ORDER BY observed_at DESC LIMIT 48",
            st["id"])
        total_readings += len(readings)
        readings_dict[st["id"]] = readings

    print(f"N+1 query took: {time.time() - start_time:.4f} seconds, {total_readings} total readings")

    start_time2 = time.time()

    station_ids = [st["id"] for st in stations]
    if station_ids:
        query = """
        SELECT station_id, observed_at, sst
        FROM (
            SELECT station_id, observed_at, sst,
                   ROW_NUMBER() OVER(PARTITION BY station_id ORDER BY observed_at DESC) as rn
            FROM readings
            WHERE station_id = ANY($1) AND sst IS NOT NULL
        ) sub
        WHERE rn <= 48
        """
        all_readings = await db.pool.fetch(query, station_ids)
        readings_dict2 = {st_id: [] for st_id in station_ids}
        for r in all_readings:
            readings_dict2[r["station_id"]].append(r)

        total_readings2 = len(all_readings)
        print(f"Window query took: {time.time() - start_time2:.4f} seconds, {total_readings2} total readings")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        asyncio.run(setup_data())
    else:
        asyncio.run(run_baseline())
