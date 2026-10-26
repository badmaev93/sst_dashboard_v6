import asyncio
import time
from unittest.mock import AsyncMock

from services.telegram_bot import _cmd_free_text


async def main():
    pool = AsyncMock()
    # Mock for counts
    pool.fetchrow.return_value = {"normal": 10, "warning": 2, "critical": 1, "offline": 0, "total": 13}

    # Mock for fetch
    async def fetch_mock(*args, **kwargs):
        query = args[0]
        if "warning" in query:
            return []
        if "requests" in query:
            return []
        if "assignments" in query:
            return []
        if "agent_activity" in query:
            return []
        if "json_build_object" in query:
            # forecast_stations
            return [
                {
                    "code": f"ST{i}",
                    "name": f"Station {i}",
                    "readings_arr": [
                        '{"observed_at": "2023-10-01 10:00:00", "sst": 10.0}',
                        '{"observed_at": "2023-10-01 11:00:00", "sst": 10.2}'
                    ]
                }
                for i in range(8)
            ]
        return []

    pool.fetch = AsyncMock(side_effect=fetch_mock)

    import services.prophet_forecast
    # Mock the actual get_station_forecast_prophet to sleep for 0.5s to simulate work
    original = services.prophet_forecast.get_station_forecast_prophet
    async def mock_prophet(*args, **kwargs):
        await asyncio.sleep(0.5)
        return {"trend": 0.1, "forecast": [10.1, 10.2, 10.3], "n_anomalies_24h": 0}
    services.prophet_forecast.get_station_forecast_prophet = mock_prophet

    start = time.perf_counter()
    reply = await _cmd_free_text(12345, "hello", pool)
    end = time.perf_counter()

    print(f"Time taken: {end - start:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
