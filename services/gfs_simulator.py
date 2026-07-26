"""
Симулятор прогнозов погоды GFS с коррекцией нейросетью AI Serendipity.

Генерирует реалистичные прогнозы температуры поверхности моря, скорости ветра и высоты волн в стиле GFS
для 20 станций мониторинга Дальнего Востока и Арктического побережья России.
Все данные сгенерированы в демонстрационных целях, но соответствуют реальной климатологии.
"""

import hashlib
import json
import math
from datetime import datetime
from typing import Any

FORECAST_HOURS = [0, 6, 12, 24, 48, 72, 120, 168, 240, 384]

STATION_CODES = [
    "TIK", "PEV", "ANA", "PRV", "MGD", "OKH", "AYN", "UKM",
    "PKC", "NKA", "DKS", "SKR", "POR", "SVG", "VAN", "KHM",
    "YSK", "KOR", "VVO", "NKH",
]

# Месячная климатология ТПО (Янв..Дек) для каждой станции.
# Основана на приблизительной широте / географии:
#   Арктические станции (TIK, PEV, ANA, DKS) ~ 70-75N -> холодно круглый год
#   Субарктика (PRV, MGD) ~ 60-63N
#   Охотское море (OKH, AYN, UKM) ~ 50-55N
#   Камчатка (PKC, NKA) ~ 53N тихоокеанская сторона
#   Сахалин (SKR, POR, KOR) ~ 47-50N
#   Приморье (SVG, VAN, KHM, VVO, NKH) ~ 42-46N
#   Якутское побережье (YSK) ~ 62N
MONTHLY_CLIM: dict[str, list[float]] = {
    "TIK": [-1.5, -1.5, -1.5, -1.5, -0.5, 2.0, 5.0, 4.0, 1.0, -0.5, -1.5, -1.5],
    "PEV": [-1.5, -1.5, -1.5, -1.5, -0.3, 2.5, 5.5, 4.5, 1.5, -0.3, -1.5, -1.5],
    "ANA": [-1.5, -1.5, -1.5, -1.4, 0.0, 3.0, 6.0, 5.0, 2.0, 0.0, -1.4, -1.5],
    "PRV": [-1.2, -1.3, -1.0, 0.0, 2.0, 5.0, 9.0, 8.5, 5.0, 1.5, -0.5, -1.0],
    "MGD": [-1.0, -1.2, -0.8, 0.5, 3.0, 6.5, 10.0, 10.5, 7.0, 3.0, 0.0, -0.8],
    "OKH": [-1.5, -1.5, -1.2, 0.0, 2.5, 6.0, 11.0, 13.0, 10.0, 5.0, 1.0, -0.5],
    "AYN": [-1.5, -1.5, -1.0, 0.5, 3.0, 7.0, 12.0, 14.0, 11.0, 6.0, 2.0, 0.0],
    "UKM": [-1.3, -1.4, -1.0, 1.0, 4.0, 8.0, 13.0, 14.5, 11.5, 6.5, 2.0, -0.3],
    "PKC": [0.5, 0.0, 0.5, 2.0, 4.5, 7.5, 11.0, 13.0, 11.0, 7.0, 3.5, 1.5],
    "NKA": [0.5, 0.0, 0.5, 2.5, 5.0, 8.0, 11.5, 13.5, 11.5, 7.5, 4.0, 1.5],
    "DKS": [-1.5, -1.5, -1.5, -1.5, -0.2, 2.0, 5.0, 4.5, 1.5, -0.2, -1.5, -1.5],
    "SKR": [-1.0, -1.2, -0.5, 2.0, 5.0, 9.0, 14.0, 16.0, 13.0, 8.0, 3.5, 0.5],
    "POR": [-0.5, -0.8, 0.0, 3.0, 6.5, 10.5, 15.0, 17.0, 14.0, 9.0, 4.5, 1.0],
    "SVG": [0.5, 0.0, 1.5, 5.0, 9.0, 13.5, 19.0, 21.0, 18.0, 12.0, 6.5, 2.5],
    "VAN": [0.5, 0.0, 1.0, 4.5, 8.5, 13.0, 18.5, 20.5, 17.5, 12.0, 6.5, 2.5],
    "KHM": [0.8, 0.3, 1.5, 5.5, 9.5, 14.0, 19.5, 21.5, 18.5, 13.0, 7.0, 3.0],
    "YSK": [-1.3, -1.4, -1.2, -0.5, 1.5, 5.0, 9.0, 8.5, 5.5, 2.0, -0.5, -1.0],
    "KOR": [-0.5, -0.8, 0.0, 3.0, 7.0, 11.0, 15.5, 17.5, 14.5, 9.0, 4.0, 1.0],
    "VVO": [1.0, 0.5, 2.0, 6.0, 10.0, 15.0, 21.0, 23.0, 20.0, 14.0, 8.0, 3.0],
    "NKH": [0.8, 0.3, 1.5, 5.0, 9.0, 14.0, 19.5, 21.5, 18.5, 13.0, 7.5, 3.0],
}

# Вектор коррекции систематической погрешности для каждой станции по месяцам (°C).
# Представляет собой систематическую погрешность, которую нейросеть AI Serendipity учится устранять.
_BIAS_SEED = {
    "TIK": 0.15, "PEV": 0.18, "ANA": 0.12, "PRV": 0.22, "MGD": 0.25,
    "OKH": 0.30, "AYN": 0.28, "UKM": 0.20, "PKC": 0.35, "NKA": 0.33,
    "DKS": 0.14, "SKR": 0.27, "POR": 0.24, "SVG": 0.32, "VAN": 0.30,
    "KHM": 0.29, "YSK": 0.19, "KOR": 0.26, "VVO": 0.38, "NKH": 0.31,
}


def _station_bias_correction(station_code: str) -> list[float]:
    """Возвращает 12-элементный вектор месячной коррекции систематической погрешности для станции."""
    base = _BIAS_SEED.get(station_code, 0.25)
    return [
        round(base * (1.0 + 0.15 * math.sin(2 * math.pi * m / 12)), 4)
        for m in range(12)
    ]


# Параметр масштаба Вейбулла для скорости ветра по станциям.
# Выше для Камчатки / открытого Тихоокеанского побережья, ниже для защищенных акваторий.
_WIND_SCALE: dict[str, float] = {
    "TIK": 8.0, "PEV": 8.5, "ANA": 7.5, "PRV": 7.0, "MGD": 7.5,
    "OKH": 8.0, "AYN": 7.5, "UKM": 7.0, "PKC": 10.0, "NKA": 10.0,
    "DKS": 8.5, "SKR": 7.0, "POR": 7.5, "SVG": 6.5, "VAN": 7.0,
    "KHM": 6.5, "YSK": 7.5, "KOR": 8.0, "VVO": 7.0, "NKH": 7.0,
}


def _hash_seed(station_code: str, issued_at: str, extra: int = 0) -> int:
    """Детерминированное зерно из кода станции + времени выпуска + дополнительного индекса."""
    raw = f"{station_code}:{issued_at}:{extra}"
    h = hashlib.sha256(raw.encode()).hexdigest()
    return int(h[:12], 16)


def _lcg_random(seed: int) -> tuple[float, int]:
    """Простой линейный конгруэнтный генератор, возвращающий (0..1, next_seed)."""
    a = 6364136223846793005
    c = 1442695040888963407
    m = 2**63
    seed = (a * seed + c) % m
    return (seed / m), seed


def _box_muller(seed: int) -> tuple[float, int]:
    """Генерация стандартной нормальной величины через преобразование Бокса-Мюллера."""
    u1, seed = _lcg_random(seed)
    u2, seed = _lcg_random(seed)
    u1 = max(u1, 1e-10)
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return z, seed


def _weibull_sample(seed: int, shape: float, scale: float) -> tuple[float, int]:
    """Генерация случайной величины с распределением Вейбулла."""
    u, seed = _lcg_random(seed)
    u = max(u, 1e-10)
    w = scale * (-math.log(u)) ** (1.0 / shape)
    return w, seed


def generate_forecast(
    station_code: str,
    lat: float,
    lon: float,
    issued_at: str | datetime,
) -> list[dict[str, Any]]:
    """
    Генерация реалистичного прогноза погоды GFS с коррекцией AI Serendipity.

    Параметры
    ----------
    station_code : str
        Один из 20 поддерживаемых кодов станций.
    lat : float
        Широта станции (градусы С.Ш.).
    lon : float
        Долгота станции (градусы В.Д.).
    issued_at : str или datetime
        Время выпуска прогноза, например "2026-04-08T00:00:00".

    Возвращает
    -------
    list[dict]
        Список словарей для каждого срока прогноза с сырыми и скорректированными значениями GFS.
    """
    if isinstance(issued_at, datetime):
        issued_str = issued_at.strftime("%Y-%m-%dT%H:%M:%S")
        month_idx = issued_at.month - 1
    else:
        issued_str = str(issued_at)
        month_idx = int(issued_str[5:7]) - 1

    clim = MONTHLY_CLIM.get(station_code, MONTHLY_CLIM["VVO"])
    sst_base = clim[month_idx]

    bias_corr_vec = _station_bias_correction(station_code)
    station_corr = bias_corr_vec[month_idx]

    wind_scale = _WIND_SCALE.get(station_code, 7.0)
    wind_shape = 2.0

    seed = _hash_seed(station_code, issued_str)
    ar1_state = 0.0
    rho = 0.85

    correction_meta = json.dumps({
        "model": "SerendipityV1",
        "version": "1.0.3",
        "rmse_reduction_pct": 31.2,
        "training_period": "2020-2025",
    })

    results: list[dict[str, Any]] = []

    for fh in FORECAST_HOURS:
        # --- SST ---
        sigma = 0.5 + 0.003 * fh
        warm_bias = 0.002 * fh

        noise_z, seed = _box_muller(seed)
        ar1_state = rho * ar1_state + math.sqrt(1 - rho**2) * noise_z
        perturbation = ar1_state * sigma

        sst_gfs = round(sst_base + perturbation + warm_bias, 2)

        corr_noise_z, seed = _box_muller(seed)
        small_noise = corr_noise_z * 0.05
        sst_corrected = round(
            sst_gfs - warm_bias - station_corr + small_noise, 2
        )

        # --- Wind speed ---
        wind_raw, seed = _weibull_sample(seed, wind_shape, wind_scale)
        wind_noise_z, seed = _box_muller(seed)
        wind_noise = wind_noise_z * (0.3 + 0.005 * fh)
        wind_speed_gfs = round(max(0.0, wind_raw + wind_noise), 1)

        if wind_speed_gfs > 15.0:
            wind_speed_corr = round(wind_speed_gfs * 0.92, 1)
        else:
            wind_speed_corr = wind_speed_gfs

        # --- Wave height ---
        wave_noise_z, seed = _box_muller(seed)
        wave_base = 0.12 * (wind_speed_gfs ** 1.4)
        wave_noise = abs(wave_noise_z) * 0.15
        wave_height_gfs = round(max(0.0, wave_base + wave_noise), 2)

        reduction_z, seed = _lcg_random(seed)
        reduction_pct = 0.05 + 0.10 * reduction_z
        wave_height_corr = round(wave_height_gfs * (1.0 - reduction_pct), 2)

        results.append({
            "forecast_hour": fh,
            "sst_gfs": sst_gfs,
            "sst_corrected": sst_corrected,
            "wind_speed_gfs": wind_speed_gfs,
            "wind_speed_corr": wind_speed_corr,
            "wave_height_gfs": wave_height_gfs,
            "wave_height_corr": wave_height_corr,
            "correction_meta": correction_meta,
        })

    return results
