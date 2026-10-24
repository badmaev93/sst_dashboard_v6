"""
Данные прогнозов GFS через Google Earth Engine (NOAA/GFS0P25).
При недоступности GEE используется сгенерированная синтетическая сетка.
"""

import io
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "gfs_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FORECAST_HOURS = [0, 6, 12, 24, 48, 72]

LON_MIN, LON_MAX = 125.0, 180.0
LAT_MIN, LAT_MAX = 40.0, 73.0
RESOLUTION = 0.25

LONS = np.arange(LON_MIN, LON_MAX + RESOLUTION / 2, RESOLUTION)
LATS = np.arange(LAT_MIN, LAT_MAX + RESOLUTION / 2, RESOLUTION)
NY, NX = len(LATS), len(LONS)

VARIABLES = [
    "temperature_2m_above_ground",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
]

# Климатология ТПО по широтам (почасовая прибрежная ТПО, °C).
# Строка = диапазон широт 40-73N.
_MONTHLY_BASE = np.array([
    # Jan   Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec
    [ 2.0,  1.5,  2.5,  6.0, 10.0, 15.0, 21.0, 23.0, 19.0, 13.0,  7.0,  3.5],  # 40N
    [ 0.5,  0.0,  1.0,  4.0,  8.0, 12.0, 17.0, 19.0, 15.0, 10.0,  5.0,  2.0],  # 50N
    [-1.0, -1.2, -0.5,  1.5,  4.0,  7.5, 11.0, 11.5,  8.0,  4.0,  0.5, -0.5],  # 60N
    [-1.5, -1.5, -1.5, -1.0,  0.5,  3.0,  6.0,  5.0,  2.0, -0.2, -1.2, -1.5],  # 70N
])
_LAT_KNOTS = np.array([40.0, 50.0, 60.0, 70.0])

# Месячная климатология ветра (средняя скорость м/с)
_MONTHLY_WIND = np.array([8.0, 7.5, 7.0, 6.0, 5.5, 5.0, 4.5, 4.5, 5.5, 6.5, 7.5, 8.0])


def _clim_sst_grid(month: int) -> np.ndarray:
    """Создание сетки климатологии ТПО по широтам для заданного месяца (1-12)."""
    m = month - 1
    base_vals = _MONTHLY_BASE[:, m]
    grid = np.zeros((NY, NX), dtype=np.float32)
    for j, lat in enumerate(LATS):
        val = float(np.interp(lat, _LAT_KNOTS, base_vals))
        grid[j, :] = val
    # Добавление градиента по долготе: немного теплее у материкового побережья (запад), холоднее на востоке
    lon_factor = np.linspace(0.5, -0.5, NX)
    grid += lon_factor[np.newaxis, :]
    return grid


def _smooth_noise(shape, scale=8):
    """Генерация пространственно-коррелированного шума через грубое прореживание и интерполяцию."""
    from scipy.ndimage import zoom as nd_zoom
    coarse_h = max(2, shape[0] // scale)
    coarse_w = max(2, shape[1] // scale)
    coarse = np.random.randn(coarse_h, coarse_w).astype(np.float32)
    zoomed = nd_zoom(coarse, (shape[0] / coarse_h, shape[1] / coarse_w), order=3)
    return zoomed[:shape[0], :shape[1]]


def _generate_fallback_grids(cycle_dt: datetime) -> dict:
    """Генерация реалистичных прогностических сеток без использования GEE."""
    month = cycle_dt.month
    seed = int(cycle_dt.strftime("%Y%m%d%H"))

    base_sst = _clim_sst_grid(month)
    base_wind_mean = float(_MONTHLY_WIND[month - 1])

    result = {}
    for fh in FORECAST_HOURS:
        rng_fh = np.random.RandomState(seed + fh)

        # Сетка ТПО: климатология + гладкое возмущение + малый шум
        sst = base_sst.copy()
        sst += _smooth_noise((NY, NX), scale=6) * (1.0 + 0.01 * fh)
        sst += rng_fh.randn(NY, NX).astype(np.float32) * 0.15
        # Небольшой дрейф со сроком прогноза
        sst += 0.002 * fh

        # Составляющие ветра: гладкие паттерны, напоминающие синоптические процессы
        wind_u = _smooth_noise((NY, NX), scale=5) * base_wind_mean * 0.6
        wind_u += rng_fh.randn(NY, NX).astype(np.float32) * 0.5

        wind_v = _smooth_noise((NY, NX), scale=5) * base_wind_mean * 0.4
        wind_v += rng_fh.randn(NY, NX).astype(np.float32) * 0.5

        result[fh] = {
            "sst": sst.astype(np.float32),
            "wind_u": wind_u.astype(np.float32),
            "wind_v": wind_v.astype(np.float32),
            "lats": LATS.astype(np.float32),
            "lons": LONS.astype(np.float32),
        }
    return result


def _try_gee_fetch(cycle_dt: datetime) -> Optional[dict]:
    """Попытка загрузки из Google Earth Engine. Возвращает None в случае ошибки."""
    try:
        import ee
        from config import GEE_PROJECT_ID
    except ImportError:
        logger.info("earthengine-api not installed, using fallback")
        return None

    try:
        ee.Initialize(project=GEE_PROJECT_ID)
    except Exception:
        try:
            ee.Authenticate()
            ee.Initialize(project=GEE_PROJECT_ID)
        except Exception as exc:
            logger.info("GEE auth failed (%s), using fallback", exc)
            return None

    try:
        region = ee.Geometry.Rectangle([LON_MIN, LAT_MIN, LON_MAX, LAT_MAX])
        cycle_str = cycle_dt.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = (cycle_dt + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")

        col = (ee.ImageCollection("NOAA/GFS0P25")
               .filterDate(cycle_str, end_str)
               .filterBounds(region))

        result = {}
        for fh in FORECAST_HOURS:
            img = col.filter(ee.Filter.eq("forecast_hours", fh)).first()
            if img is None:
                continue

            sst_band = img.select("temperature_2m_above_ground")
            u_band = img.select("u_component_of_wind_10m")
            v_band = img.select("v_component_of_wind_10m")

            def _to_np(band):
                arr = band.sampleRectangle(region=region, defaultValue=0)
                return np.array(arr.get(band.bandNames().get(0)).getInfo(), dtype=np.float32)

            sst_arr = _to_np(sst_band) - 273.15  # K -> C
            wind_u_arr = _to_np(u_band)
            wind_v_arr = _to_np(v_band)

            result[fh] = {
                "sst": sst_arr,
                "wind_u": wind_u_arr,
                "wind_v": wind_v_arr,
                "lats": LATS.astype(np.float32),
                "lons": LONS.astype(np.float32),
            }
        return result if result else None
    except Exception as exc:
        logger.warning("GEE fetch error: %s", exc)
        return None


class GFSFetcher:
    """Загружает прогностические сетки GFS из GEE с возможностью резервного перехода на синтетические данные."""

    def __init__(self):
        self._current_cycle: Optional[datetime] = None
        self._data: dict = {}

    def _cycle_time(self) -> datetime:
        """Последний прогон GFS: 00, 06, 12 или 18 UTC за вычетом 6-часовой задержки."""
        now = datetime.now(timezone.utc) - timedelta(hours=6)
        cycle_hour = (now.hour // 6) * 6
        return now.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)

    def _cache_path(self, cycle_dt: datetime, hour: int) -> Path:
        ts = cycle_dt.strftime("%Y%m%d_%H")
        return CACHE_DIR / f"gfs_{ts}_f{hour:03d}.npz"

    def _load_cache(self, cycle_dt: datetime, hour: int) -> Optional[dict]:
        p = self._cache_path(cycle_dt, hour)
        if p.exists():
            d = dict(np.load(str(p), allow_pickle=True))
            return d
        return None

    def _save_cache(self, cycle_dt: datetime, hour: int, data: dict):
        p = self._cache_path(cycle_dt, hour)
        np.savez_compressed(str(p), **data)

    def fetch_latest_cycle(self) -> dict:
        """Загружает все сроки прогноза для последнего прогона GFS.
        Возвращает {hour: {"sst": ndarray, "wind_u": ndarray, "wind_v": ndarray, "lats": ndarray, "lons": ndarray}}
        """
        cycle = self._cycle_time()
        self._current_cycle = cycle

        # Сначала проверяем кэш
        cached = {}
        all_cached = True
        for fh in FORECAST_HOURS:
            c = self._load_cache(cycle, fh)
            if c is not None:
                cached[fh] = c
            else:
                all_cached = False
        if all_cached:
            self._data = cached
            return cached

        # Пробуем GEE
        gee_data = _try_gee_fetch(cycle)
        if gee_data is not None:
            for fh, d in gee_data.items():
                self._save_cache(cycle, fh, d)
            self._data = gee_data
            return gee_data

        # Резервный вариант
        logger.info("Using fallback synthetic GFS grids for cycle %s", cycle)
        fallback = _generate_fallback_grids(cycle)
        for fh, d in fallback.items():
            self._save_cache(cycle, fh, d)
        self._data = fallback
        return fallback

    def get_cached_or_fetch(self, hour: int) -> dict:
        """Получает данные для конкретного срока прогноза с предварительной загрузкой при необходимости."""
        cycle = self._cycle_time()
        cached = self._load_cache(cycle, hour)
        if cached is not None:
            return cached

        if not self._data or self._current_cycle != cycle:
            self.fetch_latest_cycle()

        if hour in self._data:
            return self._data[hour]

        # Генерация резервных данных для одного срока
        fallback = _generate_fallback_grids(cycle)
        if hour in fallback:
            self._save_cache(cycle, hour, fallback[hour])
            return fallback[hour]

        return fallback[FORECAST_HOURS[0]]

    def extract_station_values(self, stations: list, hour: int) -> list:
        """Извлечение точечных значений для координат станций.
        stations: список словарей с ключами 'code', 'lat', 'lon'.
        Возвращает список словарей с интерполированными значениями.
        """
        data = self.get_cached_or_fetch(hour)
        lats = data["lats"]
        lons = data["lons"]
        results = []
        for st in stations:
            lat, lon = st["lat"], st["lon"]
            j = int(np.clip(np.searchsorted(lats, lat) - 1, 0, len(lats) - 2))
            i = int(np.clip(np.searchsorted(lons, lon) - 1, 0, len(lons) - 2))

            # Билинейные веса
            fj = np.clip((lat - lats[j]) / (lats[j + 1] - lats[j]), 0, 1)
            fi = np.clip((lon - lons[i]) / (lons[i + 1] - lons[i]), 0, 1)

            def _interp(arr):
                v = (arr[j, i] * (1 - fj) * (1 - fi) +
                     arr[j + 1, i] * fj * (1 - fi) +
                     arr[j, i + 1] * (1 - fj) * fi +
                     arr[j + 1, i + 1] * fj * fi)
                return float(v)

            results.append({
                "code": st.get("code", ""),
                "station_id": st.get("id"),
                "lat": lat,
                "lon": lon,
                "sst": round(_interp(data["sst"]), 2),
                "wind_u": round(_interp(data["wind_u"]), 2),
                "wind_v": round(_interp(data["wind_v"]), 2),
                "wind_speed": round(float(np.hypot(_interp(data["wind_u"]),
                                                    _interp(data["wind_v"]))), 2),
                "forecast_hour": hour,
            })
        return results

    def render_tile(self, variable: str, hour: int,
                    colormap: str = "RdYlBu_r",
                    extent: Optional[tuple] = None) -> bytes:
        """Рендеринг переменной прогноза в PNG с цветовой палитрой и прозрачностью.
        variable: 'sst', 'wind', 'pressure'
        Возвращает PNG в байтах.
        """
        data = self.get_cached_or_fetch(hour)

        if variable == "sst":
            grid = data["sst"]
            vmin, vmax = -2.0, 25.0
        elif variable == "wind":
            grid = np.hypot(data["wind_u"], data["wind_v"])
            vmin, vmax = 0.0, 20.0
            colormap = "viridis"
        elif variable == "pressure":
            # Синтезирование поля давления из дивергенции ветра
            du = np.gradient(data["wind_u"], axis=1)
            dv = np.gradient(data["wind_v"], axis=0)
            div = du + dv
            grid = 1013.25 - div * 50  # аналог гПа
            vmin, vmax = 980.0, 1040.0
            colormap = "RdBu_r"
        else:
            grid = data["sst"]
            vmin, vmax = -2.0, 25.0

        # Нормализация в диапазон 0-1
        norm = np.clip((grid - vmin) / (vmax - vmin), 0, 1)
        # Поворот, чтобы север был вверху
        norm = norm[::-1]

        lut = _build_lut(colormap)
        idx = (norm * 255).astype(np.uint8)
        rgb = lut[idx]

        # Добавление альфа-канала (прозрачно в зонах без данных / маска суши)
        alpha = np.full((*grid.shape,), 180, dtype=np.uint8)
        rgba = np.dstack([rgb, alpha])

        from PIL import Image
        img = Image.fromarray(rgba, "RGBA")

        if extent is not None:
            # Обрезка по запрошенному охвату
            e_lon_min, e_lat_min, e_lon_max, e_lat_max = extent
            lons = data["lons"]
            lats = data["lats"][::-1]
            i0 = int(np.clip(np.searchsorted(lons, e_lon_min), 0, NX - 1))
            i1 = int(np.clip(np.searchsorted(lons, e_lon_max), 0, NX))
            j0 = int(np.clip(np.searchsorted(-lats, -e_lat_max), 0, NY - 1))
            j1 = int(np.clip(np.searchsorted(-lats, -e_lat_min), 0, NY))
            img = img.crop((i0, j0, i1, j1))

        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue()

    def cleanup_old_cycles(self, max_age_hours: int = 48):
        """Удаление файлов кэша старше max_age_hours."""
        cutoff = time.time() - max_age_hours * 3600
        for f in CACHE_DIR.glob("gfs_*.npz"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                logger.info("Deleted old GFS cache: %s", f.name)

    @property
    def cycle_time(self) -> Optional[datetime]:
        return self._current_cycle

    @property
    def region_bounds(self) -> dict:
        return {
            "lon_min": LON_MIN, "lon_max": LON_MAX,
            "lat_min": LAT_MIN, "lat_max": LAT_MAX,
        }


def _build_lut(name: str) -> np.ndarray:
    """Создание таблицы поиска цветовой палитры 256x3 uint8."""
    n = 256
    lut = np.zeros((n, 3), dtype=np.uint8)
    t = np.linspace(0.0, 1.0, n)

    if name == "RdYlBu_r":
        colors = [
            (0.000, (49, 54, 149)),
            (0.125, (69, 117, 180)),
            (0.250, (116, 173, 209)),
            (0.375, (171, 217, 233)),
            (0.500, (255, 255, 191)),
            (0.625, (254, 224, 144)),
            (0.750, (253, 174, 97)),
            (0.875, (244, 109, 67)),
            (1.000, (165, 0, 38)),
        ]
    elif name == "RdBu_r":
        colors = [
            (0.000, (5, 48, 97)),
            (0.250, (33, 102, 172)),
            (0.500, (247, 247, 247)),
            (0.750, (178, 24, 43)),
            (1.000, (103, 0, 31)),
        ]
    elif name == "viridis":
        colors = [
            (0.000, (68, 1, 84)),
            (0.250, (59, 82, 139)),
            (0.500, (33, 145, 140)),
            (0.750, (94, 201, 98)),
            (1.000, (253, 231, 37)),
        ]
    else:
        colors = [
            (0.0, (0, 0, 255)),
            (0.5, (255, 255, 255)),
            (1.0, (255, 0, 0)),
        ]

    for i, v in enumerate(t):
        for k in range(len(colors) - 1):
            v0, c0 = colors[k]
            v1, c1 = colors[k + 1]
            if v0 <= v <= v1:
                f = (v - v0) / (v1 - v0) if v1 > v0 else 0.0
                lut[i] = [int(np.clip(c0[ch] + f * (c1[ch] - c0[ch]), 0, 255))
                          for ch in range(3)]
                break
    return lut


# Синглтон уровня модуля
_fetcher: Optional[GFSFetcher] = None


def get_fetcher() -> GFSFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = GFSFetcher()
    return _fetcher
