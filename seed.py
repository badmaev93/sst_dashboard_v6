"""Заполнение базы данных демонстрационными данными: станции, пользователи, 30 дней измерений, прогнозы, активность агентов."""
import asyncio
import random
import math
from datetime import datetime, timedelta, timezone

import asyncpg
from config import DATABASE_URL

STATIONS = [
    ("TIK", "Тикси", 71.64, 128.87, "Якутия"),
    ("PEV", "Певек", 69.70, 170.31, "Чукотка"),
    ("ANA", "Анадырь", 64.73, 177.52, "Чукотка"),
    ("PRV", "Провидения", 64.38, -173.30, "Чукотка"),
    ("MGD", "Магадан", 59.57, 150.78, "Магаданская обл."),
    ("OKH", "Охотск", 59.35, 143.21, "Хабаровский край"),
    ("AYN", "Аян", 56.45, 138.15, "Хабаровский край"),
    ("UKM", "Усть-Камчатск", 56.23, 162.47, "Камчатка"),
    ("PKC", "Петропавловск-Камчатский", 53.01, 158.65, "Камчатка"),
    ("NKA", "Николаевск-на-Амуре", 53.14, 140.72, "Хабаровский край"),
    ("DKS", "Де-Кастри", 51.47, 140.79, "Хабаровский край"),
    ("SKR", "Северо-Курильск", 50.68, 156.13, "Сахалинская обл."),
    ("POR", "Поронайск", 49.22, 143.11, "Сахалин"),
    ("SVG", "Советская Гавань", 48.97, 140.29, "Хабаровский край"),
    ("VAN", "Ванино", 49.09, 140.25, "Хабаровский край"),
    ("KHM", "Холмск", 47.05, 142.05, "Сахалин"),
    ("YSK", "Южно-Сахалинск", 46.97, 142.73, "Сахалин"),
    ("KOR", "Корсаков", 46.63, 142.78, "Сахалин"),
    ("VVO", "Владивосток", 43.12, 131.90, "Приморский край"),
    ("NKH", "Находка", 42.81, 132.87, "Приморский край"),
]

USERS = [
    ("admin", "admin123", "Бадмаев Олег Васильевич", "supervisor"),
    ("analyst", "analyst123", "Бадун Виктор Андреевич", "data_analyst"),
    ("observer1", "obs123", "Шпачук Денис Иванович", "observer"),
    ("engineer1", "eng123", "Козлов Дмитрий Олегович", "engineer"),
    ("observer2", "obs123", "Новикова Елена Сергеевна", "observer"),
    ("observer3", "obs123", "Петров Алексей Николаевич", "observer"),
    ("observer4", "obs123", "Сидорова Мария Павловна", "observer"),
    ("engineer2", "eng123", "Иванов Сергей Александрович", "engineer"),
    ("observer5", "obs123", "Кузнецов Андрей Викторович", "observer"),
    ("observer6", "obs123", "Морозова Анна Дмитриевна", "observer"),
    ("engineer3", "eng123", "Волков Игорь Петрович", "engineer"),
    ("observer7", "obs123", "Лебедева Ольга Игоревна", "observer"),
    ("observer8", "obs123", "Соколов Михаил Юрьевич", "observer"),
    ("engineer4", "eng123", "Попова Татьяна Сергеевна", "engineer"),
    ("observer9", "obs123", "Фёдоров Павел Андреевич", "observer"),
]

AGENT_NAMES = ["WeatherWatcher", "AnomalyDetector", "SerendipityAI", "NetworkMonitor", "QualityGuard"]
AGENT_EVENTS = [
    ("insight", "info", "Стабильная погода в регионе Камчатка", "Все станции в пределах нормы. Средняя ТПО 8.2°C."),
    ("anomaly", "warning", "Резкое повышение ТПО у станции Владивосток", "ТПО выросла на 2.3°C за последние 6 часов. Возможен апвеллинг."),
    ("status", "info", "Ежедневный отчёт сети", "Все 20 станций онлайн. Средний аптайм 99.7%."),
    ("anomaly", "critical", "Штормовое предупреждение — Охотское море", "Скорость ветра до 28 м/с у станции Магадан. Высота волн 5.2м."),
    ("insight", "info", "AI Serendipity: улучшение прогноза", "RMSE коррекции снижена на 34% для станций Курильской гряды."),
    ("status", "info", "Проверка оборудования завершена", "Автоматическая диагностика датчиков: 18/20 станций — норма, 2 — требуют внимания."),
    ("anomaly", "warning", "Аномальное давление — Чукотка", "Давление упало до 985 гПа за 3 часа. Прогноз: усиление ветра."),
    ("insight", "info", "Сезонный тренд ТПО подтверждён", "Данные за март совпадают с климатологической нормой ±0.5°C."),
]

EVENT_TYPES = ["equipment_check", "shift_change", "maintenance", "meeting", "inspection"]
EVENT_TITLES = [
    "Проверка датчиков ТПО",
    "Смена дежурства",
    "Плановое ТО метеокомплекса",
    "Совещание по итогам недели",
    "Инспекция станции",
    "Калибровка анемометра",
    "Замена батарей буя",
    "Обновление ПО станции",
]

REQUEST_TYPES = ["supply", "maintenance", "leave", "equipment"]
REQUEST_TITLES = [
    ("supply", "Запрос расходных материалов для станции", "Необходимо доставить комплект расходных материалов для гидрометеорологических наблюдений: фильтры, реагенты для анализа солёности, защитные колпаки для датчиков."),
    ("maintenance", "Плановое обслуживание метеокомплекса", "Плановое ТО метеокомплекса: чистка оптики, проверка герметичности корпусов, калибровка датчиков температуры и давления."),
    ("leave", "Заявление на отпуск — смена наблюдателя", "Заявление на ежегодный оплачиваемый отпуск. Замена наблюдателя согласована с руководителем станции."),
    ("equipment", "Замена датчика давления", "Замена датчика атмосферного давления (барометр). Текущий прибор показывает систематическое отклонение +2.5 гПа."),
    ("supply", "Доставка ГСМ на станцию", "Требуется поставка ГСМ для дизель-генератора станции. Текущий запас топлива на 2 недели работы."),
    ("maintenance", "Ремонт антенны связи", "Ремонт антенны спутниковой связи после повреждения штормовым ветром. Связь со станцией нестабильна."),
    ("equipment", "Установка нового буя", "Установка нового буя с расширенным набором сенсоров: ТПО, солёность, течения. Монтаж запланирован на период затишья."),
    ("leave", "Отгул по семейным обстоятельствам", "Отгул по семейным обстоятельствам. Дежурство передано сменному наблюдателю."),
]


def _sst_clim(lat, month):
    clim = {
        70: [-1.8,-1.8,-1.8,-1.5,-0.5,2.0,5.0,6.0,4.0,1.0,-0.5,-1.5],
        55: [0.0,0.0,0.5,3.0,6.0,10.0,14.0,16.0,13.0,8.0,3.0,1.0],
        45: [2.0,1.5,3.0,6.0,10.0,14.0,20.0,22.0,19.0,13.0,7.0,3.0],
    }
    idx = month - 1
    bands = sorted(clim.keys())
    if lat >= bands[-1]:
        return clim[bands[-1]][idx]
    if lat <= bands[0]:
        return clim[bands[0]][idx]
    for i in range(len(bands) - 1):
        if bands[i] <= lat < bands[i + 1]:
            t = (lat - bands[i]) / (bands[i + 1] - bands[i])
            return clim[bands[i]][idx] * (1 - t) + clim[bands[i + 1]][idx] * t
    return clim[bands[0]][idx]


async def main():
    print("Connecting to NeonDB...")
    conn = await asyncpg.connect(DATABASE_URL)

    # --- Пользователи ---
    print("Seeding users...")
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user_ids = []
    for username, password, full_name, role in USERS:
        uid = await conn.fetchval(
            """INSERT INTO users (username, password_hash, full_name, role)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (username) DO UPDATE SET full_name=EXCLUDED.full_name
               RETURNING id""",
            username, pwd.hash(password), full_name, role
        )
        user_ids.append(uid)
    print(f"  {len(user_ids)} users")

    # --- Станции ---
    print("Seeding stations...")
    station_ids = []
    station_coords = {}

    records = await conn.fetch(
        """INSERT INTO stations (code, name, lat, lon, region, status)
           SELECT code, name, lat, lon, region, 'normal'
           FROM unnest($1::text[], $2::text[], $3::float[], $4::float[], $5::text[])
           AS u(code, name, lat, lon, region)
           ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name
           RETURNING id, lat, lon""",
        [s[0] for s in STATIONS],
        [s[1] for s in STATIONS],
        [s[2] for s in STATIONS],
        [s[3] for s in STATIONS],
        [s[4] for s in STATIONS]
    )
    for row in records:
        sid = row["id"]
        station_ids.append(sid)
        station_coords[sid] = (row["lat"], row["lon"])

    print(f"  {len(station_ids)} stations")

    # --- Измерения (30 дней, по часам) ---
    print("Seeding readings (30 days hourly)... this may take a minute...")
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    readings_data = []
    for sid in station_ids:
        lat, lon = station_coords[sid]
        t = start
        while t <= now:
            month = t.month
            hour = t.hour
            sst_base = _sst_clim(lat, month)
            sst = round(sst_base + random.gauss(0, 0.5) + 0.3 * math.sin(2 * math.pi * hour / 24), 2)
            temp_air = round(sst_base + random.gauss(-1, 1.5) + 2.0 * math.sin(2 * math.pi * (hour - 6) / 24), 2)
            wind_speed = round(max(0, random.gauss(6.0, 3.0)), 1)
            wind_dir = random.randint(0, 359)
            wave_height = round(max(0.1, wind_speed * 0.15 + random.gauss(0, 0.3)), 2)
            wave_period = round(max(2.0, wave_height * 1.5 + random.gauss(4.0, 1.0)), 1)
            pressure = round(random.gauss(1013.0, 5.0), 1)
            humidity = round(min(100, max(30, random.gauss(75, 10))), 1)
            visibility = round(max(0.5, random.gauss(15, 5)), 1)
            status = "normal"
            if wind_speed > 15 or wave_height > 3.0:
                status = "warning"
            if wind_speed > 25 or wave_height > 5.0:
                status = "critical"
            readings_data.append((sid, t, sst, temp_air, wave_height, wave_period, wind_speed, wind_dir, pressure, visibility, humidity, status))
            t += timedelta(hours=1)

    # Пакетная вставка
    await conn.executemany(
        """INSERT INTO readings (station_id, observed_at, sst, temp_air, wave_height, wave_period,
           wind_speed, wind_dir, pressure, visibility, humidity, status)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
        readings_data
    )
    print(f"  {len(readings_data)} readings")

    # --- Прогнозы GFS ---
    print("Seeding GFS forecasts...")
    forecast_hours = [0, 6, 12, 24, 48, 72, 120, 168, 240, 384]
    fc_data = []
    for sid in station_ids:
        lat, _ = station_coords[sid]
        for day_offset in range(0, 30, 3):
            issued = now - timedelta(days=day_offset)
            month = issued.month
            sst_base = _sst_clim(lat, month)
            for fh in forecast_hours:
                bias = 0.002 * fh
                sst_gfs = round(sst_base + bias + random.gauss(0, 0.8), 2)
                correction = random.gauss(0.3, 0.1)
                sst_corr = round(sst_gfs - correction, 2)
                ws_gfs = round(max(0, random.gauss(7, 4)), 1)
                ws_corr = round(max(0, ws_gfs - random.gauss(0.5, 0.2)), 1)
                wh_gfs = round(max(0.1, ws_gfs * 0.15 + random.gauss(0, 0.3)), 2)
                wh_corr = round(max(0.1, wh_gfs - random.gauss(0.1, 0.05)), 2)
                meta = {"model": "SerendipityV1", "rmse_reduction": round(random.uniform(0.25, 0.40), 2)}
                fc_data.append((sid, issued, fh, sst_gfs, sst_corr, ws_gfs, ws_corr, wh_gfs, wh_corr, meta))

    # Преобразование в json для полей JSONB
    import json
    for row in fc_data:
        await conn.execute(
            """INSERT INTO gfs_forecasts (station_id, issued_at, forecast_hour, sst_gfs, sst_corrected,
               wind_speed_gfs, wind_speed_corr, wave_height_gfs, wave_height_corr, correction_meta)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)""",
            row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], json.dumps(row[9])
        )
    print(f"  {len(fc_data)} forecasts")

    # --- Персонал ---
    print("Seeding personnel...")
    positions = ["Наблюдатель", "Инженер-метеоролог", "Техник", "Старший наблюдатель"]
    # Каждому пользователю назначается по 2 станции для лучшего покрытия
    for i, uid in enumerate(user_ids[1:], start=0):
        for offset in [0, len(station_ids) // 2]:
            sid = station_ids[(i + offset) % len(station_ids)]
            await conn.execute(
                "INSERT INTO personnel (user_id, station_id, position, phone) VALUES ($1,$2,$3,$4)",
                uid, sid, positions[i % len(positions)], f"+7900{random.randint(1000000,9999999)}"
            )

    # --- Активность агентов ---
    print("Seeding agent activity...")
    for i in range(60):
        agent = random.choice(AGENT_NAMES)
        evt = random.choice(AGENT_EVENTS)
        created = now - timedelta(hours=random.randint(0, 720))
        await conn.execute(
            """INSERT INTO agent_activity (agent_name, event_type, severity, title, body, metadata, created_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7)""",
            agent, evt[0], evt[1], evt[2], evt[3],
            json.dumps({"station": random.choice([s[0] for s in STATIONS])}),
            created
        )
    print("  60 agent events")

    # --- События календаря ---
    print("Seeding calendar events...")
    for i in range(30):
        evt_type = random.choice(EVENT_TYPES)
        title = random.choice(EVENT_TITLES)
        sid = random.choice(station_ids)
        uid = random.choice(user_ids)
        starts = now + timedelta(days=random.randint(-15, 30), hours=random.randint(8, 16))
        ends = starts + timedelta(hours=random.randint(1, 4))
        colors = {"equipment_check": "#2196F3", "shift_change": "#4CAF50", "maintenance": "#FF9800",
                  "meeting": "#9C27B0", "inspection": "#F44336"}
        await conn.execute(
            """INSERT INTO calendar_events (title, description, event_type, station_id, created_by, starts_at, ends_at, color)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
            title, f"Автоматически созданное событие #{i+1}", evt_type, sid, uid, starts, ends,
            colors.get(evt_type, "#607D8B")
        )
    print("  30 calendar events")

    # --- Заявки ---
    print("Seeding requests...")
    statuses = ["pending", "in_progress", "signed", "completed", "rejected"]
    for i in range(20):
        req_type, title, description = random.choice(REQUEST_TITLES)
        sid = random.choice(station_ids)
        created_by = random.choice(user_ids[1:])
        assigned_to = user_ids[0]  # supervisor
        status = random.choice(statuses)
        created = now - timedelta(days=random.randint(0, 30))
        signed_at = created + timedelta(days=random.randint(1, 3)) if status in ("signed", "completed") else None
        await conn.execute(
            """INSERT INTO requests (station_id, created_by, assigned_to, title, description, req_type, status, priority, created_at, signed_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            sid, created_by, assigned_to, title, description,
            req_type, status, random.choice(["low", "normal", "high"]), created, signed_at
        )
    print("  20 requests")

    # --- Проверки оборудования ---
    print("Seeding equipment checks...")
    equipment_list = ["Анемометр", "Барометр", "Термометр ТПО", "Гигрометр", "Радар волнения", "Буй метеорологический", "Антенна связи"]
    for i in range(40):
        sid = random.choice(station_ids)
        uid = random.choice(user_ids[2:])
        equip = random.choice(equipment_list)
        result = random.choices(["pass", "warning", "fail"], weights=[0.7, 0.2, 0.1])[0]
        checked = now - timedelta(days=random.randint(0, 30))
        notes = "" if result == "pass" else "Требуется внимание" if result == "warning" else "Необходима замена"
        await conn.execute(
            "INSERT INTO equipment_checks (station_id, checked_by, equipment, result, notes, checked_at) VALUES ($1,$2,$3,$4,$5,$6)",
            sid, uid, equip, result, notes, checked
        )
    print("  40 equipment checks")

    # --- Задачи ---
    print("Seeding tasks...")
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    task_data = [
        ("Проверка калибровки анемометра — ст. Владивосток", "P1", 60, 0, False, "equipment_check"),
        ("Подготовка еженедельного отчёта", "P1", 120, 0, False, "report"),
        ("Замена батарей на буе — ст. Магадан", "P1", 90, 1, False, "maintenance"),
        ("Валидация данных ТПО за неделю", "P2", 45, 0, True, "analysis"),
        ("Обновление ПО метеокомплекса — ст. Тикси", "P2", 60, 2, False, "maintenance"),
        ("Согласование графика вахт на май", "P2", 30, 0, False, "meeting"),
        ("Осмотр антенны связи — ст. Певек", "P1", 45, 3, False, "inspection"),
        ("Отправка заявки на расходные материалы", "P3", 20, 0, True, "supply"),
        ("Анализ аномалий давления — Чукотка", "P2", 90, 0, False, "analysis"),
        ("Резервное копирование базы данных", "P3", 15, 0, True, "maintenance"),
        ("Проверка датчиков влажности — ст. Анадырь", "P2", 40, 0, False, "equipment_check"),
        ("Подготовка презентации для совещания", "P2", 60, 1, False, "report"),
        ("Обсуждение результатов коррекции прогноза", "P3", 30, 0, False, "meeting"),
        ("Тестирование нового алгоритма SerendipityAI", "P2", 120, 0, False, "analysis"),
        ("Составление акта инспекции — ст. Охотск", "P1", 45, -1, True, "inspection"),
        ("Замена термодатчика ТПО — ст. Корсаков", "P2", 60, 2, False, "maintenance"),
        ("Обновление документации API", "P3", 90, 0, False, "report"),
        ("Проверка связи со спутником — ст. Камчатка", "P1", 30, 0, False, "equipment_check"),
    ]
    for title, priority, est_min, day_offset, completed, task_type in task_data:
        due = today + timedelta(days=day_offset)
        sid = random.choice(station_ids) if "ст." in title else None
        uid = random.choice(user_ids)
        await conn.execute(
            """INSERT INTO tasks (title, priority, estimated_minutes, due_date, station_id, assigned_to, completed)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            title, priority, est_min, due, sid, uid, completed
        )
    print(f"  {len(task_data)} tasks")

    # --- Блоки фокусировки ---
    print("Seeding focus blocks...")
    focus_data = [
        ("Глубокая работа", "09:00", "12:00", "#3b82f6", None, True),
        ("Совещание", "14:00", "15:00", "#7c3aed", None, True),
        ("Полевые работы", "08:00", "13:00", "#059669", 2, True),
        ("Анализ данных", "15:00", "17:00", "#06b6d4", None, True),
        ("Планирование", "17:00", "18:00", "#f59e0b", 1, True),
        ("Обзор инцидентов", "13:00", "14:00", "#ef4444", 5, True),
    ]
    from datetime import time as dt_time
    def parse_time(s):
        h, m = s.split(':')
        return dt_time(int(h), int(m))

    for title, start_t, end_t, color, dow, recurring in focus_data:
        uid = user_ids[0]
        await conn.execute(
            """INSERT INTO focus_blocks (title, start_time, end_time, color, user_id, day_of_week, recurring)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            title, parse_time(start_t), parse_time(end_t), color, uid, dow, recurring
        )
    print(f"  {len(focus_data)} focus blocks")

    # --- Дежурства (график смен) ---
    print("Seeding duty assignments...")
    personnel_rows = await conn.fetch("SELECT id, station_id, position FROM personnel")
    if personnel_rows:
        duty_roles = ["Наблюдатель", "Старший наблюдатель", "Инженер-метеоролог", "Техник"]
        for day_offset in range(-7, 15):
            day = today + timedelta(days=day_offset)
            for p in personnel_rows:
                # Каждый сотрудник дежурит раз в 2-3 дня
                if (p["id"] + day_offset) % 3 != 0:
                    continue
                shift_start = day.replace(hour=8)
                shift_end = day.replace(hour=20)
                role = p["position"] if p["position"] in duty_roles else duty_roles[p["id"] % len(duty_roles)]
                await conn.execute(
                    """INSERT INTO assignments (personnel_id, station_id, shift_start, shift_end, role_on_duty)
                       VALUES ($1, $2, $3, $4, $5)""",
                    p["id"], p["station_id"], shift_start, shift_end, role
                )
        print("  duty assignments seeded")
    else:
        print("  no personnel found, skipping assignments")

    await conn.close()
    print("\nSeed completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
