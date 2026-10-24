import asyncio
import time

class MockPool:
    async def fetch(self, query, *args):
        if 'SELECT id, code, name FROM stations' in query:
            return [{'id': i, 'code': f'ST{i}', 'name': f'Station {i}'} for i in range(100)]
        elif 'SELECT observed_at, sst FROM readings' in query:
            # Simulate N+1 query latency
            await asyncio.sleep(0.005)
            return [{'observed_at': '2023-01-01T00:00:00Z', 'sst': 15.0} for _ in range(48)]
        elif 'ROW_NUMBER() OVER' in query:
            # Simulate single query latency
            await asyncio.sleep(0.02) # Slightly longer for the bigger query
            results = []
            station_ids = args[0]
            for st_id in station_ids:
                results.extend([{'station_id': st_id, 'observed_at': '2023-01-01T00:00:00Z', 'sst': 15.0} for _ in range(48)])
            return results
        return []

async def test_current_approach():
    pool = MockPool()
    stations = await pool.fetch('SELECT id, code, name FROM stations ORDER BY id')

    start = time.perf_counter()
    for st in stations:
        readings = await pool.fetch(
            '''SELECT observed_at, sst FROM readings
            WHERE station_id = $1 AND sst IS NOT NULL
            ORDER BY observed_at DESC LIMIT 48''',
            st['id'])
        readings_list = [
            {'observed_at': str(r['observed_at']), 'sst': float(r['sst'])}
            for r in readings
        ]
    return time.perf_counter() - start

async def test_optimized_approach():
    pool = MockPool()
    stations = await pool.fetch('SELECT id, code, name FROM stations ORDER BY id')

    start = time.perf_counter()
    station_ids = [st['id'] for st in stations]

    all_readings = await pool.fetch("""
        SELECT station_id, observed_at, sst
        FROM (
            SELECT station_id, observed_at, sst,
                   ROW_NUMBER() OVER(PARTITION BY station_id ORDER BY observed_at DESC) as rn
            FROM readings
            WHERE station_id = ANY($1) AND sst IS NOT NULL
        ) t
        WHERE rn <= 48
        ORDER BY station_id, observed_at DESC
    """, station_ids)

    from collections import defaultdict
    readings_by_station = defaultdict(list)
    for r in all_readings:
        readings_by_station[r["station_id"]].append({
            "observed_at": str(r["observed_at"]),
            "sst": float(r["sst"])
        })

    for st in stations:
        readings_list = readings_by_station.get(st["id"], [])

    return time.perf_counter() - start

async def main():
    t1 = await test_current_approach()
    t2 = await test_optimized_approach()
    print(f"Current: {t1:.4f}s")
    print(f"Optimized: {t2:.4f}s")
    print(f"Improvement: {t1/t2:.2f}x")

if __name__ == '__main__':
    asyncio.run(main())
