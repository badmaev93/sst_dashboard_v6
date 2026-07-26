"""Получение реальных метеоданных из API Open-Meteo Marine + Weather для дальневосточных станций."""
import logging
import httpx

logger = logging.getLogger(__name__)

MARINE_API = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_API = "https://api.open-meteo.com/v1/forecast"


async def fetch_station_reading(lat: float, lon: float) :
    """Получение текущих метеорологических и морских данных для одной станции из Open-Meteo."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            marine_resp, weather_resp = await _fetch_both(client, lat, lon)

        marine = marine_resp.get("current", {}) if marine_resp else {}
        weather = weather_resp.get("current", {}) if weather_resp else {}

        sst = marine.get("sea_surface_temperature")
        wave_height = marine.get("wave_height")
        wave_period = marine.get("wave_period")
        wave_dir = marine.get("wave_direction")

        temp_air = weather.get("temperature_2m")
        wind_speed_kmh = weather.get("wind_speed_10m")
        wind_dir = weather.get("wind_direction_10m")
        pressure = weather.get("surface_pressure")
        humidity = weather.get("relative_humidity_2m")
        visibility_m = weather.get("visibility")

        wind_speed = round(wind_speed_kmh / 3.6, 1) if wind_speed_kmh is not None else None
        visibility = round(visibility_m / 1000, 1) if visibility_m is not None else None

        if sst is None and temp_air is None:
            return None

        status = "normal"
        if (wind_speed or 0) > 15 or (wave_height or 0) > 3.0:
            status = "warning"
        if (wind_speed or 0) > 25 or (wave_height or 0) > 5.0:
            status = "critical"

        return {
            "sst": round(sst, 2) if sst is not None else None,
            "temp_air": round(temp_air, 2) if temp_air is not None else None,
            "wave_height": round(wave_height, 2) if wave_height is not None else None,
            "wave_period": round(wave_period, 1) if wave_period is not None else None,
            "wind_speed": round(wind_speed, 1) if wind_speed is not None else None,
            "wind_dir": int(wind_dir) if wind_dir is not None else (int(wave_dir) if wave_dir is not None else None),
            "pressure": round(pressure, 1) if pressure is not None else None,
            "visibility": visibility,
            "humidity": round(humidity, 1) if humidity is not None else None,
            "status": status,
        }
    except Exception as e:
        logger.error("Open-Meteo fetch failed for (%.2f, %.2f): %s", lat, lon, e)
        return None


async def fetch_bulk_readings(stations: list) -> dict:
    """Получение измерений для нескольких станций. Возвращает {station_id: reading_dict}."""
    results = {}
    lats = ",".join(str(s["lat"]) for s in stations)
    lons = ",".join(str(s["lon"]) for s in stations)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            marine_task = client.get(MARINE_API, params={
                "latitude": lats,
                "longitude": lons,
                "current": "wave_height,wave_direction,wave_period,sea_surface_temperature",
            })
            weather_task = client.get(WEATHER_API, params={
                "latitude": lats,
                "longitude": lons,
                "current": "temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m,visibility",
            })
            marine_resp, weather_resp = await marine_task, await weather_task

        marine_data = marine_resp.json() if marine_resp.is_success else []
        weather_data = weather_resp.json() if weather_resp.is_success else []

        if not isinstance(marine_data, list):
            marine_data = [marine_data]
        if not isinstance(weather_data, list):
            weather_data = [weather_data]

        for i, st in enumerate(stations):
            marine = marine_data[i].get("current", {}) if i < len(marine_data) else {}
            weather = weather_data[i].get("current", {}) if i < len(weather_data) else {}

            sst = marine.get("sea_surface_temperature")
            wave_height = marine.get("wave_height")
            wave_period = marine.get("wave_period")
            wave_dir = marine.get("wave_direction")
            temp_air = weather.get("temperature_2m")
            wind_speed_kmh = weather.get("wind_speed_10m")
            wind_dir = weather.get("wind_direction_10m")
            pressure = weather.get("surface_pressure")
            humidity = weather.get("relative_humidity_2m")
            visibility_m = weather.get("visibility")

            wind_speed = round(wind_speed_kmh / 3.6, 1) if wind_speed_kmh is not None else None
            visibility = round(visibility_m / 1000, 1) if visibility_m is not None else None

            if sst is None and temp_air is None:
                continue

            status = "normal"
            if (wind_speed or 0) > 15 or (wave_height or 0) > 3.0:
                status = "warning"
            if (wind_speed or 0) > 25 or (wave_height or 0) > 5.0:
                status = "critical"

            results[st["id"]] = {
                "sst": round(sst, 2) if sst is not None else None,
                "temp_air": round(temp_air, 2) if temp_air is not None else None,
                "wave_height": round(wave_height, 2) if wave_height is not None else None,
                "wave_period": round(wave_period, 1) if wave_period is not None else None,
                "wind_speed": wind_speed,
                "wind_dir": int(wind_dir) if wind_dir is not None else (int(wave_dir) if wave_dir is not None else None),
                "pressure": round(pressure, 1) if pressure is not None else None,
                "visibility": visibility,
                "humidity": round(humidity, 1) if humidity is not None else None,
                "status": status,
            }
    except Exception as e:
        logger.error("Open-Meteo bulk fetch failed: %s", e)

    return results


async def _fetch_both(client, lat, lon):
    """Fetch marine and weather data concurrently for a single point."""
    marine_resp = None
    weather_resp = None
    try:
        r = await client.get(MARINE_API, params={
            "latitude": lat, "longitude": lon,
            "current": "wave_height,wave_direction,wave_period,sea_surface_temperature",
        })
        if r.is_success:
            marine_resp = r.json()
    except Exception as e:
        logger.warning("Marine API error: %s", e)

    try:
        r = await client.get(WEATHER_API, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m,visibility",
        })
        if r.is_success:
            weather_resp = r.json()
    except Exception as e:
        logger.warning("Weather API error: %s", e)

    return marine_resp, weather_resp
