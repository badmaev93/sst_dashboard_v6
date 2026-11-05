"""
Прогноз GFS со смонтированной файловой системы или сетевого ресурса SMB.

Основной (Вариант B): монтирование ресурса ОС, настройка GFS_LOCAL_PATH:
  sudo mount -t cifs //10.11.60.25/meteo /mnt/meteo -o username=...,password=...,uid=$(id -u)
  GFS_LOCAL_PATH=/mnt/meteo/data/NOAA/NCEP/FTPPRD/pub/data/nccf/com/gfs/prod0p25.sfc

Резервный: чтение через smbprotocol (требуются GFS_SMB_USER / GFS_SMB_PASS).

Структура каталогов: <base>/<YYYY>/<MM>/<DD>/00/gfs.t00z.pgrb2.0p25.f<FFF>
Срок прогона всегда 00. Последняя дата определяется листингом дерева каталогов.
"""

import logging
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Если задано, считывается со смонтированной файловой системы (Вариант B). Имеет приоритет перед SMB.
GFS_LOCAL_PATH = os.getenv("GFS_LOCAL_PATH", "")

# Резервные параметры SMB
SMB_HOST = os.getenv("GFS_SMB_HOST", "10.11.60.25")
SMB_SHARE = os.getenv("GFS_SMB_SHARE", "meteo")
SMB_USER = os.getenv("GFS_SMB_USER", "")
SMB_PASS = os.getenv("GFS_SMB_PASS", "")
SMB_DOMAIN = os.getenv("GFS_SMB_DOMAIN", "")
SMB_BASE = os.getenv(
    "GFS_SMB_BASE",
    "data/NOAA/NCEP/FTPPRD/pub/data/nccf/com/gfs/prod0p25.sfc",
)

FORECAST_HOURS = [0, 6, 12, 24, 48, 72]

LON_MIN, LON_MAX = 125.0, 180.0
LAT_MIN, LAT_MAX = 40.0, 73.0
RESOLUTION = 0.25

LONS = np.arange(LON_MIN, LON_MAX + RESOLUTION / 2, RESOLUTION)
LATS = np.arange(LAT_MIN, LAT_MAX + RESOLUTION / 2, RESOLUTION)
NY, NX = len(LATS), len(LONS)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "gfs_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Бэкенд файловой системы (Вариант B — смонтированный ресурс)
# ---------------------------------------------------------------------------

def _local_find_latest_date(base: Path) -> Optional[tuple[str, str, str]]:
    """Поиск наиболее свежей даты (оптимизировано: поиск от текущей даты назад)."""
    if not base.is_dir():
        logger.error("GFS_LOCAL_PATH does not exist or is not mounted: %s", base)
        return None

    # Оптимизация: пробуем искать назад от текущей даты
    current = datetime.now(timezone.utc)
    for i in range(30):
        d = current - timedelta(days=i)
        year = d.strftime("%Y")
        month = d.strftime("%m")
        day = d.strftime("%d")

        hour_dir = base / year / month / day / "00"
        if hour_dir.is_dir() and any(hour_dir.iterdir()):
            logger.info("GFS latest (optimized): %s/%s/%s/00", year, month, day)
            return year, month, day

    # Fallback: обход дерева, если ничего не найдено за последние 30 дней
    years = sorted((d.name for d in base.iterdir() if d.is_dir() and d.name.isdigit()), reverse=True)
    for year in years:
        months = sorted((d.name for d in (base / year).iterdir()
                         if d.is_dir() and d.name.isdigit()), reverse=True)
        for month in months:
            days = sorted((d.name for d in (base / year / month).iterdir()
                           if d.is_dir() and d.name.isdigit()), reverse=True)
            for day in days:
                hour_dir = base / year / month / day / "00"
                if hour_dir.is_dir() and any(hour_dir.iterdir()):
                    logger.info("GFS latest (fallback): %s/%s/%s/00", year, month, day)
                    return year, month, day
    return None


def _local_read_file(base: Path, year: str, month: str, day: str, hour: int) -> Optional[bytes]:
    fname = f"gfs.t00z.pgrb2.0p25.f{hour:03d}.grb2"
    fpath = base / year / month / day / "00" / fname
    if not fpath.exists():
        logger.warning("GFS file not found: %s", fpath)
        return None
    logger.info("GFS: reading %s (%.1f MB)", fpath, fpath.stat().st_size / 1e6)
    return fpath.read_bytes()


# ---------------------------------------------------------------------------
# Бэкенд SMB (резервный, когда GFS_LOCAL_PATH не задан)
# ---------------------------------------------------------------------------

def _smb_path(*parts: str) -> str:
    inner = "\\".join(p.replace("/", "\\").strip("\\") for p in parts if p)
    return f"\\\\{SMB_HOST}\\{SMB_SHARE}\\{inner}"


def _smb_register():
    import smbclient
    try:
        smbclient.register_session(
            SMB_HOST,
            username=SMB_USER or None,
            password=SMB_PASS or None,
            domain=SMB_DOMAIN or None,
        )
    except Exception as exc:
        logger.debug("SMB register_session: %s", exc)


def _smb_listdir(smb_p: str) -> list[str]:
    import smbclient
    try:
        return sorted(e.name for e in smbclient.scandir(smb_p)
                      if e.name not in (".", ".."))
    except Exception as exc:
        logger.warning("SMB listdir %s: %s", smb_p, exc)
        return []


def _smb_find_latest_date() -> Optional[tuple[str, str, str]]:
    _smb_register()
    base = _smb_path(SMB_BASE)

    # Оптимизация: пробуем искать назад от текущей даты
    current = datetime.now(timezone.utc)
    for i in range(30):
        d = current - timedelta(days=i)
        year = d.strftime("%Y")
        month = d.strftime("%m")
        day = d.strftime("%d")

        hour_dir = f"{base}\\{year}\\{month}\\{day}\\00"
        if _smb_listdir(hour_dir):
            logger.info("GFS latest (SMB, optimized): %s/%s/%s/00", year, month, day)
            return year, month, day

    # Fallback: обход дерева, если ничего не найдено за последние 30 дней
    years = [y for y in reversed(_smb_listdir(base)) if y.isdigit() and len(y) == 4]
    for year in years:
        months = [m for m in reversed(_smb_listdir(f"{base}\\{year}"))
                  if m.isdigit() and len(m) == 2]
        for month in months:
            days = [d for d in reversed(_smb_listdir(f"{base}\\{year}\\{month}"))
                    if d.isdigit() and len(d) == 2]
            for day in days:
                hour_dir = f"{base}\\{year}\\{month}\\{day}\\00"
                if _smb_listdir(hour_dir):
                    logger.info("GFS latest (SMB, fallback): %s/%s/%s/00", year, month, day)
                    return year, month, day
    return None


def _smb_read_file(year: str, month: str, day: str, hour: int) -> Optional[bytes]:
    import smbclient
    fname = f"gfs.t00z.pgrb2.0p25.f{hour:03d}.grb2"
    p = _smb_path(SMB_BASE, year, month, day, "00", fname)
    try:
        with smbclient.open_file(p, mode="rb") as fh:
            return fh.read()
    except Exception as exc:
        logger.warning("SMB read %s: %s", p, exc)
        return None


# ---------------------------------------------------------------------------
# Единый интерфейс чтения
# ---------------------------------------------------------------------------

def find_latest_date() -> Optional[tuple[str, str, str]]:
    if GFS_LOCAL_PATH:
        return _local_find_latest_date(Path(GFS_LOCAL_PATH))
    return _smb_find_latest_date()


def read_grib_bytes(year: str, month: str, day: str, hour: int) -> Optional[bytes]:
    if GFS_LOCAL_PATH:
        return _local_read_file(Path(GFS_LOCAL_PATH), year, month, day, hour)
    return _smb_read_file(year, month, day, hour)


# ---------------------------------------------------------------------------
# Парсинг GRIB2 (cfgrib)
# ---------------------------------------------------------------------------

def _parse_grib2(data: bytes, forecast_hour: int) -> Optional[dict]:
    try:
        import cfgrib
    except ImportError:
        logger.error("cfgrib not installed")
        return None

    with tempfile.NamedTemporaryFile(suffix=".grb2", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    result = None
    try:
        dsets = cfgrib.open_datasets(tmp_path)
        t2m = _extract_var(dsets, ["t2m", "2t"], level=2)
        u10 = _extract_var(dsets, ["u10", "10u"], level=10)
        v10 = _extract_var(dsets, ["v10", "10v"], level=10)

        if t2m is None or u10 is None or v10 is None:
            logger.warning("fh=%d: missing variable(s) in GRIB2 — found: %s",
                           forecast_hour,
                           [v for ds in dsets for v in ds.data_vars])
            return None

        t_sub = _subset(t2m)
        u_sub = _subset(u10)
        v_sub = _subset(v10)

        if t_sub is None:
            return None

        t_arr = t_sub.values.astype(np.float32)
        if t_arr.mean() > 100:   # Кельвины → Цельсии
            t_arr -= 273.15

        result = {
            "sst": t_arr,
            "wind_u": u_sub.values.astype(np.float32),
            "wind_v": v_sub.values.astype(np.float32),
            "lats": LATS.astype(np.float32),
            "lons": LONS.astype(np.float32),
        }
    except Exception as exc:
        logger.error("GRIB2 parse error (fh=%d): %s", forecast_hour, exc)
    finally:
        try:
            os.unlink(tmp_path)
            for suf in (".923a8.idx", ".idx"):
                sidx = tmp_path + suf
                if os.path.exists(sidx):
                    os.unlink(sidx)
        except OSError:
            pass

    return result


def _extract_var(dsets, short_names: list, level: int):
    for ds in dsets:
        for name in short_names:
            if name not in ds:
                continue
            da = ds[name]
            # Кельвины → Цельсии
            for coord_name in ("heightAboveGround", "level"):
                if coord_name in da.coords:
                    if abs(float(da.coords[coord_name]) - level) > 0.5:
                        break
            else:
                return da
            # Несовпадение уровня — продолжаем поиск
    return None


def _subset(da):
    """Обрезает область и интерполирует на сетку LATS/LONS."""
    try:
        lat_dim = next(d for d in da.dims if "lat" in d.lower())
        lon_dim = next(d for d in da.dims if "lon" in d.lower())

        lats_coord = da.coords[lat_dim].values
        if lats_coord[0] > lats_coord[-1]:
            da = da.sel({lat_dim: slice(LAT_MAX, LAT_MIN),
                         lon_dim: slice(LON_MIN, LON_MAX)})
        else:
            da = da.sel({lat_dim: slice(LAT_MIN, LAT_MAX),
                         lon_dim: slice(LON_MIN, LON_MAX)})

        return da.interp({lat_dim: LATS, lon_dim: LONS}, method="linear")
    except Exception as exc:
        logger.error("Subset error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Кэш (.npz, аналогичный формат gee_gfs)
# ---------------------------------------------------------------------------

def _cache_path(date_str: str, hour: int) -> Path:
    return CACHE_DIR / f"gfs_smb_{date_str}_f{hour:03d}.npz"


def _load_cache(date_str: str, hour: int) -> Optional[dict]:
    p = _cache_path(date_str, hour)
    if p.exists():
        try:
            return dict(np.load(str(p), allow_pickle=True))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save_cache(date_str: str, hour: int, data: dict):
    np.savez_compressed(str(_cache_path(date_str, hour)), **data)


# ---------------------------------------------------------------------------
# Публичный сборщик данных
# ---------------------------------------------------------------------------

class SMBGFSFetcher:
    """
    Загружает файлы GFS GRIB2 со смонтированного ресурса (или SMB) и кэширует их как .npz.
    При недоступности выполняет переход на синтетические сетки.
    """

    def __init__(self):
        self._latest_date: Optional[tuple[str, str, str]] = None
        self._data: dict = {}

    def fetch_latest(self) -> dict:
        try:
            latest = find_latest_date()
        except Exception as exc:
            logger.error("GFS source unavailable: %s", exc)
            latest = None

        if latest is None:
            logger.warning("GFS: no data found, using synthetic fallback")
            self._data = self._synthetic_fallback()
            return self._data

        self._latest_date = latest
        year, month, day = latest
        date_str = year + month + day

        result = {}
        for fh in FORECAST_HOURS:
            # Сначала проверяем кэш
            cached = _load_cache(date_str, fh)
            if cached is not None:
                result[fh] = cached
                continue

            raw = read_grib_bytes(year, month, day, fh)
            if raw is None:
                logger.warning("GFS fh=%d: file unavailable, synthetic fallback", fh)
                result[fh] = self._synthetic_hour(fh)
                continue

            parsed = _parse_grib2(raw, fh)
            if parsed is None:
                result[fh] = self._synthetic_hour(fh)
                continue

            _save_cache(date_str, fh, parsed)
            result[fh] = parsed

        self._data = result
        return result

    def get_hour(self, hour: int) -> dict:
        if hour not in self._data:
            self.fetch_latest()
        return self._data.get(hour, self._synthetic_hour(hour))

    @property
    def cycle_info(self) -> dict:
        if self._latest_date:
            y, m, d = self._latest_date
            src = "local-fs" if GFS_LOCAL_PATH else "SMB"
            return {"date": f"{y}-{m}-{d}", "cycle": "00Z", "source": f"{src}/GFS0P25"}
        return {"date": None, "cycle": "00Z", "source": "synthetic"}

    def _synthetic_fallback(self) -> dict:
        from services.gee_gfs import _generate_fallback_grids
        return _generate_fallback_grids(datetime.now(timezone.utc))

    def _synthetic_hour(self, hour: int) -> dict:
        from services.gee_gfs import _generate_fallback_grids
        grids = _generate_fallback_grids(datetime.now(timezone.utc))
        return grids.get(hour, next(iter(grids.values())))


_fetcher: Optional[SMBGFSFetcher] = None


def get_smb_fetcher() -> SMBGFSFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = SMBGFSFetcher()
    return _fetcher
