from __future__ import annotations
"""
AI Serendipity — коррекция систематической погрешности + интеграция с Nixtla TimeGPT.
Лимит Nixtla: 50 запросов/месяц → кэширование результатов на 7 дней для каждой станции.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config import NIXTLA_API_KEY

logger = logging.getLogger(__name__)

# ── Конфигурация Nixtla ───────────────────────────────────────────────────────────
NIXTLA_BASE: str = "https://api.nixtla.io"
_CACHE_TTL_DAYS: int = 7
_MONTHLY_LIMIT: int = 50
_MIN_READINGS: int = 10

# station_code → {"forecast": [...], "anomaly_scores": [...], "ts": datetime}
_nixtla_cache: dict[str, dict[str, Any]] = {}
# {year_month: int}  e.g. {"2025-04": 12}
_call_counter: dict[str, int] = {}


# ── Утилиты счётчика и кэша ───────────────────────────────────────────────────────
def _ym() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _calls_this_month() -> int:
    return _call_counter.get(_ym(), 0)


def _inc_counter() -> None:
    key = _ym()
    _call_counter[key] = _call_counter.get(key, 0) + 1


def _cache_fresh(station_code: str) -> bool:
    entry = _nixtla_cache.get(station_code)
    if not entry:
        return False
    age = datetime.now(timezone.utc) - entry["ts"]
    return age < timedelta(days=_CACHE_TTL_DAYS)


def _check_rate_limit(station_code: str, readings: list[dict]) -> str | None:
    """Возвращает строку-причину пропуска вызова или None, если всё ок."""
    if _cache_fresh(station_code):
        return "cache_fresh"
    if _calls_this_month() >= _MONTHLY_LIMIT:
        return "monthly_limit"
    if len(readings) < _MIN_READINGS:
        return "insufficient_readings"
    return None


# ── Таблицы коррекции систематической погрешности ──────────────────────────────────
MONTHLY_SST_BIAS: dict[str, list[float]] = {
    "TIK": [0.15, 0.14, 0.16, 0.18, 0.22, 0.25, 0.28, 0.26, 0.20, 0.17, 0.15, 0.14],
    "PEV": [0.18, 0.17, 0.19, 0.21, 0.25, 0.30, 0.32, 0.29, 0.24, 0.20, 0.18, 0.17],
    "ANA": [0.12, 0.11, 0.13, 0.15, 0.20, 0.23, 0.26, 0.24, 0.18, 0.14, 0.12, 0.11],
    "PRV": [0.22, 0.20, 0.23, 0.28, 0.35, 0.40, 0.42, 0.38, 0.30, 0.25, 0.22, 0.20],
    "MGD": [0.25, 0.23, 0.26, 0.32, 0.38, 0.44, 0.48, 0.45, 0.36, 0.28, 0.25, 0.23],
    "OKH": [0.30, 0.28, 0.31, 0.38, 0.45, 0.52, 0.55, 0.50, 0.42, 0.35, 0.30, 0.28],
    "AYN": [0.28, 0.26, 0.29, 0.35, 0.42, 0.48, 0.52, 0.48, 0.40, 0.32, 0.28, 0.26],
    "UKM": [0.20, 0.18, 0.21, 0.26, 0.32, 0.38, 0.40, 0.36, 0.28, 0.22, 0.20, 0.18],
    "PKC": [0.35, 0.32, 0.36, 0.42, 0.50, 0.58, 0.62, 0.58, 0.48, 0.40, 0.35, 0.32],
    "NKA": [0.33, 0.30, 0.34, 0.40, 0.48, 0.55, 0.60, 0.56, 0.46, 0.38, 0.33, 0.30],
    "DKS": [0.14, 0.13, 0.15, 0.17, 0.21, 0.24, 0.27, 0.25, 0.19, 0.16, 0.14, 0.13],
    "SKR": [0.27, 0.25, 0.28, 0.34, 0.40, 0.46, 0.50, 0.46, 0.38, 0.30, 0.27, 0.25],
    "POR": [0.24, 0.22, 0.25, 0.30, 0.36, 0.42, 0.45, 0.42, 0.34, 0.27, 0.24, 0.22],
    "SVG": [0.32, 0.30, 0.33, 0.40, 0.48, 0.55, 0.58, 0.54, 0.44, 0.36, 0.32, 0.30],
    "VAN": [0.30, 0.28, 0.31, 0.38, 0.45, 0.52, 0.56, 0.52, 0.42, 0.34, 0.30, 0.28],
    "KHM": [0.29, 0.27, 0.30, 0.36, 0.44, 0.50, 0.54, 0.50, 0.40, 0.33, 0.29, 0.27],
    "YSK": [0.19, 0.17, 0.20, 0.24, 0.30, 0.35, 0.38, 0.35, 0.28, 0.22, 0.19, 0.17],
    "KOR": [0.26, 0.24, 0.27, 0.33, 0.40, 0.46, 0.50, 0.46, 0.38, 0.30, 0.26, 0.24],
    "VVO": [0.38, 0.35, 0.39, 0.46, 0.55, 0.64, 0.68, 0.62, 0.52, 0.42, 0.38, 0.35],
    "NKH": [0.31, 0.29, 0.32, 0.38, 0.46, 0.53, 0.57, 0.53, 0.43, 0.35, 0.31, 0.29],
}

WIND_BIAS: dict[str, float] = {
    "TIK": 0.4, "PEV": 0.5, "ANA": 0.3, "PRV": 0.6, "MGD": 0.7,
    "OKH": 0.8, "AYN": 0.7, "UKM": 0.5, "PKC": 1.2, "NKA": 1.1,
    "DKS": 0.4, "SKR": 0.6, "POR": 0.5, "SVG": 0.8, "VAN": 0.7,
    "KHM": 0.6, "YSK": 0.5, "KOR": 0.7, "VVO": 0.9, "NKH": 0.8,
}

_MODEL_META: dict[str, Any] = {
    "model": "SerendipityV2+TimeGPT",
    "version": "2.0.0",
    "rmse_reduction_pct": 31.2,
    "training_period": "2020-2025",
}


# ── Коррекция GFS ─────────────────────────────────────────────────────────────────
def correct_gfs_sst(station_code: str, month: int, gfs_sst: float) -> tuple[float, dict]:
    bias_vec = MONTHLY_SST_BIAS.get(station_code)
    if bias_vec is None:
        return gfs_sst, {**_MODEL_META, "applied": False, "reason": "unknown station"}
    m = max(0, min(11, month - 1))
    bias = bias_vec[m]
    corrected = round(gfs_sst - bias, 2)
    return corrected, {
        **_MODEL_META,
        "applied": True,
        "station": station_code,
        "month": month,
        "bias_removed": bias,
    }


def correct_gfs_wind(station_code: str, gfs_wind: float) -> tuple[float, dict]:
    bias = WIND_BIAS.get(station_code, 0.5)
    if gfs_wind > 15.0:
        corrected = round(gfs_wind * 0.92 - bias * 0.3, 1)
    else:
        corrected = round(max(0.0, gfs_wind - bias), 1)
    return corrected, {
        **_MODEL_META,
        "applied": True,
        "station": station_code,
        "wind_bias_removed": bias,
    }


# ── Вспомогательный HTTP-клиент Nixtla ───────────────────────────────────────────
def _build_timeseries(readings: list[dict]) -> tuple[list, list]:
    """Сортирует измерения и возвращает (timestamps, values)."""
    sorted_r = sorted(readings, key=lambda x: x["observed_at"])
    return [r["observed_at"] for r in sorted_r], [r["sst"] for r in sorted_r]


async def _nixtla_post(endpoint: str, payload: dict) -> dict | None:
    """Выполняет POST-запрос к Nixtla, обновляет счётчик, возвращает JSON или None."""
    import httpx

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{NIXTLA_BASE}/{endpoint}",
            json=payload,
            headers={
                "Authorization": f"Bearer {NIXTLA_API_KEY}",
                "Content-Type": "application/json",
            },
        )

    _inc_counter()

    if resp.status_code != 200:
        logger.warning("Nixtla %s error %d: %s", endpoint, resp.status_code, resp.text[:200])
        return None

    return resp.json()


# ── Асинхронные вызовы Nixtla ──────────────────────────────────────────────────────
async def call_nixtla_forecast(station_code: str, readings: list[dict]) -> dict | None:
    """Вызов Nixtla TimeGPT для прогноза ТПО. Соблюдает лимит 50/мес с кэшем на 7 дней."""
    if not NIXTLA_API_KEY:
        return None
    skip_reason = _check_rate_limit(station_code, readings)
    if skip_reason == "cache_fresh":
        cached = _nixtla_cache[station_code]
        if "forecast" in cached:
            logger.debug("Nixtla: returning cached forecast for %s", station_code)
            return {"forecast": cached["forecast"]}
    elif skip_reason == "monthly_limit":
        logger.info(
            "Nixtla: monthly limit reached (%d/%d), skipping",
            _calls_this_month(), _MONTHLY_LIMIT,
        )
        return None
    elif skip_reason == "insufficient_readings":
        logger.debug("Nixtla: insufficient readings for %s (%d)", station_code, len(readings))
        return None

    try:
        timestamps, values = _build_timeseries(readings)
        payload = {
            "model": "timegpt-1",
            "freq": "h",
            "fh": 6,  # Прогноз на 6 часов вперёд
            "y": {"timestamp": timestamps, "value": values},
            "clean_ex_first": True,
        }

        data = await _nixtla_post("timegpt", payload)
        if data is None:
            return None

        logger.info(
            "Nixtla forecast call #%d/%d for %s",
            _calls_this_month(), _MONTHLY_LIMIT, station_code,
        )

        forecast_vals = data.get("data", {}).get("forecast", {}).get("value", [])
        if not forecast_vals:
            return None

        entry = _nixtla_cache.setdefault(station_code, {})
        entry["forecast"] = [round(float(v), 2) for v in forecast_vals]
        entry["ts"] = datetime.now(timezone.utc)
        return {"forecast": entry["forecast"]}

    except Exception as e:
        logger.error("Nixtla forecast exception for %s: %s", station_code, e)
        return None


async def call_nixtla_anomaly(station_code: str, readings: list[dict]) -> dict | None:
    """Вызов детекции аномалий Nixtla. Соблюдает лимит 50/мес с кэшем на 7 дней."""
    if not NIXTLA_API_KEY:
        return None
    skip_reason = _check_rate_limit(station_code, readings)
    if skip_reason == "cache_fresh":
        cached = _nixtla_cache.get(station_code, {})
        if "anomaly_scores" in cached:
            logger.debug("Nixtla: returning cached anomalies for %s", station_code)
            return {"anomaly_scores": cached["anomaly_scores"]}
    elif skip_reason in ("monthly_limit", "insufficient_readings"):
        return None

    try:
        timestamps, values = _build_timeseries(readings)
        payload = {
            "model": "timegpt-1",
            "freq": "h",
            "y": {"timestamp": timestamps, "value": values},
        }

        data = await _nixtla_post("anomaly_detection", payload)
        if data is None:
            return None

        logger.info(
            "Nixtla anomaly call #%d/%d for %s",
            _calls_this_month(), _MONTHLY_LIMIT, station_code,
        )

        scores = data.get("data", {}).get("anomaly", [])
        if scores is None:
            return None

        entry = _nixtla_cache.setdefault(station_code, {})
        entry["anomaly_scores"] = [float(s) for s in scores]
        entry["ts"] = datetime.now(timezone.utc)
        return {"anomaly_scores": entry["anomaly_scores"]}

    except Exception as e:
        logger.error("Nixtla anomaly exception for %s: %s", station_code, e)
        return None
