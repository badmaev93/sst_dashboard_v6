"""Фоновый планировщик для почасовой генерации данных, симуляции событий и опроса Telegram."""
import logging
import asyncio
import random
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REQUEST_TEMPLATES = [
    ("Плановое техническое обслуживание датчика ТПО", "maintenance", "normal", "Плановое ТО: чистка оптики, проверка герметичности, калибровка датчиков температуры и давления."),
    ("Аномальное значение температуры поверхности океана — требуется проверка", "equipment", "high", "Зафиксировано отклонение ТПО более 3°C от климатической нормы. Необходимо проверить работоспособность датчика."),
    ("Замена поплавкового буя в районе станции", "equipment", "high", "Буй повреждён в результате шторма. Требуется замена на резервный с расширенным набором сенсоров."),
    ("Калибровка анемометра и гидрологических датчиков", "maintenance", "normal", "Плановая калибровка метеооборудования. Последняя калибровка — 3 месяца назад."),
    ("Проверка линии связи со станцией", "maintenance", "normal", "Периодические обрывы связи. Необходимо проверить антенну и кабельную инфраструктуру."),
    ("Внеплановый ремонт измерительного оборудования", "equipment", "high", "Датчик волнения вышел из строя. Запасной комплект на складе станции."),
    ("Поставка расходных материалов для гидрологических наблюдений", "supply", "normal", "Запас фильтров и реагентов для анализа солёности на исходе. Необходима поставка до конца месяца."),
    ("Обновление ПО системы сбора данных", "maintenance", "normal", "Доступна новая версия ПО метеокомплекса с улучшенной обработкой данных."),
    ("Ликвидация последствий шторма — восстановление буйковой станции", "maintenance", "high", "Шторм 8 баллов повредил крепление буя. Требуется выезд ремонтной бригады."),
    ("Плановая замена аккумуляторных батарей", "maintenance", "normal", "Ёмкость текущих батарей снизилась до 45%. Плановая замена согласно регламенту."),
]

# столбцы agent_activity: agent_name, event_type (NOT NULL), severity, title, body
AGENT_EVENT_TEMPLATES = [
    ("SerendipityV2", "anomaly", "Обнаружена аномалия ТПО +2.1°C относительно климатической нормы",
     "warning", "Значение превышает климатическую норму для данного сезона"),
    ("SerendipityV2", "forecast", "Прогноз: ожидается шторм 8-10 баллов через 12-24ч",
     "critical", "GFS модель с нейрокоррекцией AI Serendipity"),
    ("DataQC", "telemetry", "Пропуск в данных станции — нет телеметрии более 2 часов",
     "warning", "Возможен сбой канала связи или отключение питания"),
    ("SerendipityV2", "anomaly", "Обнаружена положительная аномалия ТПО — возможное проявление течения Куросио",
     "info", "Устойчивое отклонение +1.8°C в течение 3 суток"),
    ("DataQC", "telemetry", "Восстановление связи со станцией после перерыва",
     "info", "Данные снова поступают в штатном режиме"),
    ("SerendipityV2", "quality", "Точность GFS-прогноза снизилась: RMSE > 0.8°C за последние 24ч",
     "warning", "Рекомендуется проверка входных данных модели"),
]

_scheduler_started = False

def start_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    async def _generate_hourly():
        while True:
            try:
                import db
                if db.pool is None:
                    await asyncio.sleep(60)
                    continue

                from services.data_generator import fetch_bulk_readings
                now = datetime.now(timezone.utc)

                rows = await db.pool.fetch("SELECT id, code, lat, lon FROM stations")
                stations = [{"id": r["id"], "code": r["code"], "lat": float(r["lat"]), "lon": float(r["lon"])} for r in rows]

                readings = await fetch_bulk_readings(stations)
                count = 0
                for st in stations:
                    r = readings.get(st["id"])
                    if not r:
                        continue
                    await db.pool.execute("""
                        INSERT INTO readings (station_id, observed_at, sst, temp_air,
                            wave_height, wave_period, wind_speed, wind_dir,
                            pressure, visibility, humidity, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """, st['id'], now, r['sst'], r['temp_air'],
                        r['wave_height'], r['wave_period'],
                        r['wind_speed'], r['wind_dir'],
                        r['pressure'], r['visibility'],
                        r['humidity'], r['status'])

                    await db.pool.execute(
                        "UPDATE stations SET status = $1 WHERE id = $2",
                        r['status'], st['id'])
                    count += 1

                logger.info("Open-Meteo: fetched %d/%d station readings at %s", count, len(stations), now.isoformat())
            except Exception as e:
                logger.error("Hourly generation failed: %s", e)

            await asyncio.sleep(3600)

    async def _telegram_polling():
        """Long-polling для обновлений Telegram (localhost не может получать вебхуки)."""
        import httpx
        from config import TELEGRAM_BOT_TOKEN
        if not TELEGRAM_BOT_TOKEN:
            logger.info("Telegram polling skipped: no token")
            return

        api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
        offset = 0
        logger.info("Telegram polling started")

        # Удаление существующего вебхука и сброс ожидающих обновлений
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"{api}/deleteWebhook", json={"drop_pending_updates": True})
                logger.info("Telegram webhook deleted, pending updates dropped")
        except Exception as e:
            logger.warning("Failed to delete webhook: %s", e)

        await asyncio.sleep(2)

        while True:
            try:
                import db
                if db.pool is None:
                    await asyncio.sleep(5)
                    continue

                async with httpx.AsyncClient(timeout=35) as client:
                    resp = await client.get(f"{api}/getUpdates", params={
                        "offset": offset, "timeout": 30, "allowed_updates": ["message"]
                    })
                    if resp.status_code == 409:
                        logger.warning("Telegram 409 conflict — retrying in 5s")
                        await asyncio.sleep(5)
                        continue
                    if resp.is_success:
                        data = resp.json()
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            try:
                                from services.telegram_bot import handle_telegram_update
                                await handle_telegram_update(update, db.pool)
                            except Exception as e:
                                logger.error("Telegram handler error: %s", e)
            except Exception as e:
                logger.error("Telegram polling error: %s", e)
                await asyncio.sleep(5)

    async def _generate_requests():
        """Симуляция реалистичных заявок, как если бы операторы подавали их в реальном времени."""
        # Начальная задержка для готовности БД
        await asyncio.sleep(120)
        while True:
            try:
                import db
                if db.pool is None:
                    await asyncio.sleep(60)
                    continue

                stations = await db.pool.fetch("SELECT id FROM stations ORDER BY random() LIMIT 2")
                supervisor = await db.pool.fetchrow(
                    "SELECT id FROM users WHERE role = 'supervisor' LIMIT 1")
                operator = await db.pool.fetchrow(
                    "SELECT id FROM users WHERE role IN ('operator', 'observer') LIMIT 1")

                if not stations or not operator:
                    await asyncio.sleep(300)
                    continue

                n_requests = random.randint(1, 2)
                for st in list(stations)[:n_requests]:
                    title, req_type, priority, description = random.choice(REQUEST_TEMPLATES)
                    await db.pool.execute("""
                        INSERT INTO requests
                            (station_id, created_by, assigned_to, title, description, req_type, status, priority, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7, now())
                        ON CONFLICT DO NOTHING
                    """, st["id"], operator["id"],
                        supervisor["id"] if supervisor else None,
                        title, description, req_type, priority)
                    logger.info("Simulated request created: %s", title[:40])

            except Exception as e:
                logger.error("Request generation failed: %s", e)

            # Пауза 2-4 часа между пакетами заявок
            await asyncio.sleep(random.randint(7200, 14400))

    async def _generate_agent_events():
        """Периодическая генерация событий активности AI-агентов."""
        await asyncio.sleep(180)
        while True:
            try:
                import db
                if db.pool is None:
                    await asyncio.sleep(60)
                    continue

                agent_name, event_type, title, severity, body = random.choice(AGENT_EVENT_TEMPLATES)
                await db.pool.execute("""
                    INSERT INTO agent_activity (agent_name, event_type, severity, title, body, created_at)
                    VALUES ($1, $2, $3, $4, $5, now())
                """, agent_name, event_type, severity, title, body)
                logger.info("Simulated agent event: [%s] %s", severity, title[:50])

            except Exception as e:
                logger.error("Agent event generation failed: %s", e)

            await asyncio.sleep(random.randint(3600, 7200))  # 1-2 hours

    async def _daily_monitoring():
        """
        Ежедневный запуск прогноза Prophet + детекция аномалий для всех станций.
        Отправляет сводку в Telegram супервайзерам в 08:00 UTC.
        """
        import datetime as _dt
        # Начальная задержка: ожидание до 08:00 UTC следующего дня
        now = _dt.datetime.now(_dt.timezone.utc)
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if target <= now:
            target += _dt.timedelta(days=1)
        wait_sec = (target - now).total_seconds()
        logger.info("Daily monitoring: first run in %.0f seconds (at 08:00 UTC)", wait_sec)
        await asyncio.sleep(wait_sec)

        while True:
            try:
                import db
                if db.pool is None:
                    await asyncio.sleep(300)
                    continue

                logger.info("Daily monitoring run started")
                stations = await db.pool.fetch(
                    "SELECT id, code, name FROM stations ORDER BY id")

                station_ids = [st["id"] for st in stations]
                from collections import defaultdict
                readings_by_station = defaultdict(list)

                if station_ids:
                    all_readings = await db.pool.fetch("""
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

                    for r in all_readings:
                        readings_by_station[r["station_id"]].append(
                            {"observed_at": str(r["observed_at"]), "sst": float(r["sst"])}
                        )

                total_anomalies = 0
                for st in stations:
                    try:
                        readings_list = readings_by_station.get(st["id"], [])

                        from services.prophet_forecast import get_station_forecast_prophet
                        fc = await get_station_forecast_prophet(
                            st["code"], readings_list, periods=6)

                        n_anom = fc.get("n_anomalies_24h", 0)
                        total_anomalies += n_anom

                        if n_anom > 0:
                            # Логирование события аномалии в agent_activity
                            await db.pool.execute("""
                                INSERT INTO agent_activity
                                    (agent_name, event_type, severity, title, body, created_at)
                                VALUES ($1, 'anomaly', $2, $3, $4, now())
                            """, "ProphetMonitor",
                                "warning" if n_anom < 3 else "critical",
                                f"Prophet: {n_anom} аномалий ТПО за 24ч — {st['name']}",
                                f"Метод: Prophet | Тренд: {fc.get('trend', 0):+.2f}°C/сут")

                    except Exception as e:
                        logger.error("Daily monitoring failed for station %s: %s",
                                     st["code"], e)

                logger.info("Daily monitoring: %d total anomalies across %d stations",
                            total_anomalies, len(stations))

                # Отправка сводки в Telegram
                try:
                    from services.telegram_bot import send_daily_summary
                    await send_daily_summary(db.pool)
                except Exception as e:
                    logger.error("Daily Telegram summary failed: %s", e)

            except Exception as e:
                logger.error("Daily monitoring error: %s", e)

            await asyncio.sleep(86400)  # 24 hours

    loop = asyncio.get_event_loop()
    loop.create_task(_generate_hourly())
    loop.create_task(_generate_requests())
    loop.create_task(_generate_agent_events())
    loop.create_task(_daily_monitoring())
    loop.create_task(_telegram_polling())
    logger.info("Scheduler started: hourly readings + requests + agent events + daily monitoring")
