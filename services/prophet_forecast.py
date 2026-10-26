"""
Прогнозирование ТПО на базе Prophet для прибрежных станций.
- Метод прогнозирования по умолчанию (бесплатный, локальный запуск, без лимитов API)
- Используется для ежедневного мониторинга: детекция аномалий + 7-дневный прогноз
- TimeGPT (AI Serendipity) используется по запросу из forecast.js
"""
import logging
import math
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Кэш: station_code → {forecast, anomalies, ts}
_prophet_cache: dict = {}
_CACHE_TTL_HOURS = 23  # обновление раз в сутки


def _cache_fresh(station_code: str) -> bool:
    entry = _prophet_cache.get(station_code)
    if not entry:
        return False
    age = datetime.now(timezone.utc) - entry["ts"]
    return age < timedelta(hours=_CACHE_TTL_HOURS)


def run_prophet_forecast(readings: list[dict], periods: int = 6) -> dict:
    """
    Запуск Prophet на исторических измерениях ТПО.
    readings: список {"observed_at": ISO str, "sst": float}, сначала самые свежие.
    periods: количество будущих часов для прогнозирования.
    Возвращает {"forecast": [float], "anomalies": [bool], "trend": float, "upper": [float], "lower": [float]}
    """
    if len(readings) < 10:
        return _fallback_forecast(readings, periods)

    try:
        import pandas as pd
        from prophet import Prophet

        # Подготовка датафрейма (Prophet ожидает ds, y)
        sorted_r = sorted(readings, key=lambda x: x["observed_at"])
        df = pd.DataFrame({
            "ds": pd.to_datetime([r["observed_at"] for r in sorted_r]),
            "y": [float(r["sst"]) for r in sorted_r],
        })
        df = df.dropna()

        if len(df) < 10:
            return _fallback_forecast(readings, periods)

        # Обучение Prophet с сезонностью, подходящей для почасовых океанографических данных
        m = Prophet(
            changepoint_prior_scale=0.05,  # консервативные изменения тренда для ТПО
            seasonality_prior_scale=0.5,
            interval_width=0.90,
            daily_seasonality=True,
            weekly_seasonality=False,
            yearly_seasonality=len(df) > 720,  # только если есть данные более чем за 1 месяц
        )
        m.fit(df)

        # Прогноз на следующие `periods` часов
        future = m.make_future_dataframe(periods=periods, freq="h")
        forecast_df = m.predict(future)

        # Извлечение только будущих прогнозов
        future_fc = forecast_df.tail(periods)
        forecast_vals = [round(float(v), 2) for v in future_fc["yhat"].values]
        upper_vals   = [round(float(v), 2) for v in future_fc["yhat_upper"].values]
        lower_vals   = [round(float(v), 2) for v in future_fc["yhat_lower"].values]

        # Детекция аномалий: точки за пределами 90% доверительного интервала
        hist_fc = forecast_df.iloc[: len(df)]
        anomalies = [
            bool(y < yhat_lower or y > yhat_upper)
            for y, yhat_lower, yhat_upper in zip(
                df["y"].values,
                hist_fc["yhat_lower"].values,
                hist_fc["yhat_upper"].values,
            )
        ]

        # Тренд: наклон за последние 24 часа прогноза
        trend = round(float(forecast_df["trend"].iloc[-1] - forecast_df["trend"].iloc[-24]), 3) \
            if len(forecast_df) >= 24 else 0.0

        n_anomalies = sum(anomalies[-24:])  # последние 24 часа
        logger.info("Prophet forecast complete: %d points, %d anomalies in last 24h", len(df), n_anomalies)

        return {
            "forecast": forecast_vals,
            "upper": upper_vals,
            "lower": lower_vals,
            "anomalies": anomalies,
            "n_anomalies_24h": n_anomalies,
            "trend": trend,
            "method": "prophet",
        }

    except ImportError:
        logger.warning("prophet not installed, using fallback forecast")
        return _fallback_forecast(readings, periods)
    except Exception as e:
        logger.error("Prophet forecast error: %s", e)
        return _fallback_forecast(readings, periods)


def _fallback_forecast(readings: list[dict], periods: int) -> dict:
    """Простая линейная экстраполяция, когда Prophet недоступен."""
    if not readings:
        return {"forecast": [0.0] * periods, "upper": [0.5] * periods,
                "lower": [-0.5] * periods, "anomalies": [], "n_anomalies_24h": 0,
                "trend": 0.0, "method": "linear_fallback"}

    vals = [float(r["sst"]) for r in sorted(readings, key=lambda x: x["observed_at"])
            if r.get("sst") is not None]
    if not vals:
        base = 5.0
    else:
        base = vals[-1]
        # Оценка тренда по последним 12 значениям
        if len(vals) >= 12:
            trend = (vals[-1] - vals[-12]) / 12
        else:
            trend = 0.0

    forecast = [round(base + trend * (i + 1), 2) for i in range(periods)]
    upper = [round(v + 0.5, 2) for v in forecast]
    lower = [round(v - 0.5, 2) for v in forecast]

    # Простая аномалия: значения > 2 стандартных отклонений от среднего
    if len(vals) >= 5:
        mean = sum(vals) / len(vals)
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        threshold = max(std * 2, 0.5)
        anomalies = [abs(v - mean) > threshold for v in vals]
    else:
        anomalies = []

    return {"forecast": forecast, "upper": upper, "lower": lower,
            "anomalies": anomalies, "n_anomalies_24h": sum(anomalies[-24:]),
            "trend": round(trend if len(vals) >= 12 else 0.0, 3),
            "method": "linear_fallback"}


async def get_station_forecast_prophet(station_code: str, readings: list[dict],
                                        periods: int = 6) -> dict:
    """Получение прогноза Prophet с кэшированием. Вызывается из ежедневного планировщика и по запросу."""
    if _cache_fresh(station_code):
        logger.debug("Prophet: returning cached forecast for %s", station_code)
        return _prophet_cache[station_code]["result"]

    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, run_prophet_forecast, readings, periods)

    _prophet_cache[station_code] = {
        "result": result,
        "ts": datetime.now(timezone.utc),
    }
    return result
