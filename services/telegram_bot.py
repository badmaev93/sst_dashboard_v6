from __future__ import annotations
"""
@serendipity_sst_bot — расширенный Telegram бот.
Функции:
  /start        — меню
  /status       — сводка по сети
  /station VVO  — данные станции + GigaChat анализ
  /forecast VVO — Prophet прогноз + AI Serendipity (TimeGPT по запросу)
  /pending      — неподписанные заявки (для supervisor)
  /summary      — краткая ежедневная сводка
  /events       — знаменательные события (аномалии, критические события)
  /help         — помощь
"""
import logging
import httpx

from config import TELEGRAM_BOT_TOKEN
import db

logger = logging.getLogger(__name__)
TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

SUPERVISOR_CHAT_IDS: set[int] = set()  # заполняется из БД при выполнении /start


async def send_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set")
        return
    async with httpx.AsyncClient(timeout=15) as client:
        body = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            body["parse_mode"] = parse_mode
        resp = await client.post(f"{TG_API}/sendMessage", json=body)
        if not resp.is_success:
            logger.error("Telegram sendMessage failed: %s", resp.text[:200])


async def send_chat_action(chat_id: int, action: str = "typing"):
    if not TELEGRAM_BOT_TOKEN:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{TG_API}/sendChatAction", json={"chat_id": chat_id, "action": action})


async def broadcast_to_supervisors(text: str):
    """Отправка сообщения всем супервайзерам."""
    if not SUPERVISOR_CHAT_IDS:
        return
    for cid in list(SUPERVISOR_CHAT_IDS):
        await send_message(cid, text)


async def handle_telegram_update(update: dict, pool):
    if not update.get("message"):
        return {"ok": True}

    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if not text:
        return {"ok": True}

    parts = text.split()
    cmd = parts[0].lower().split("@")[0]  # удаление имени бота из /cmd@botname

    handlers = {
        "/start":    _cmd_start,
        "/help":     _cmd_help,
        "/status":   _cmd_status,
        "/summary":  _cmd_summary,
        "/pending":  _cmd_pending,
        "/events":   _cmd_events,
    }

    if cmd in handlers:
        reply = await handlers[cmd](chat_id, pool)
    elif cmd == "/station":
        code = parts[1].upper() if len(parts) > 1 else None
        reply = await _cmd_station(chat_id, code, pool)
    elif cmd == "/forecast":
        code = parts[1].upper() if len(parts) > 1 else None
        reply = await _cmd_forecast(chat_id, code, pool)
    else:
        # Передача произвольного текста ИИ — обычный текст без парсинга HTML
        await send_chat_action(chat_id)
        reply = await _cmd_free_text(chat_id, text, pool)
        if reply:
            await send_message(chat_id, reply, parse_mode="")
        return {"ok": True}

    if reply:
        await send_message(chat_id, reply)
    return {"ok": True}


# ── Обработчики команд ──────────────────────────────────────────────────────────

async def _cmd_start(chat_id: int, pool) -> str:
    # Регистрация, если пользователь является супервайзером
    if pool:
        row = await pool.fetchrow(
            "SELECT role FROM users WHERE telegram_chat_id = $1", chat_id)
        if row and row["role"] == "supervisor":
            SUPERVISOR_CHAT_IDS.add(chat_id)

    return (
        "🌊 <b>AI Serendipity — Мониторинг станций ДВ</b>\n\n"
        "<b>Команды:</b>\n"
        "/status — обзор сети станций\n"
        "/summary — ежедневная сводка с анализом\n"
        "/station VVO — данные станции + ИИ анализ\n"
        "/forecast VVO — прогноз ТПО (Prophet + AI Serendipity)\n"
        "/pending — неподписанные заявки ✍\n"
        "/events — знаменательные события и аномалии 🔔\n"
        "/help — подробная справка\n\n"
        "<i>Бот использует GigaChat и AI Serendipity (TimeGPT)</i>"
    )


async def _cmd_help(chat_id: int, pool) -> str:
    return (
        "📖 <b>Справка по боту</b>\n\n"
        "<b>/status</b> — сводка по всем станциям сети (счётчики норма/внимание/критично)\n\n"
        "<b>/summary</b> — ежедневный бюллетень с ИИ анализом (GigaChat)\n\n"
        "<b>/station VVO</b> — текущие данные конкретной станции (ТПО, ветер, волны, давление) "
        "+ краткий ИИ комментарий\n\n"
        "<b>/forecast VVO</b> — прогноз ТПО на 6 часов методом Prophet. "
        "AI Serendipity (TimeGPT) применяется для коррекции GFS-данных\n\n"
        "<b>/pending</b> — список заявок, ожидающих подписи руководителя\n\n"
        "<b>/events</b> — аномалии и важные события за последние 48ч\n\n"
        "<i>Коды станций: VVO, PKC, OKH, MGD, PEV и др.</i>"
    )


async def _cmd_status(chat_id: int, pool) -> str:
    if not pool:
        return "⚠️ БД недоступна"
    counts = await pool.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'normal')   AS normal,
            COUNT(*) FILTER (WHERE status = 'warning')  AS warning,
            COUNT(*) FILTER (WHERE status = 'critical') AS critical,
            COUNT(*) FILTER (WHERE status = 'offline')  AS offline,
            COUNT(*) AS total
        FROM stations
    """)
    open_req = await pool.fetchval(
        "SELECT COUNT(*) FROM requests WHERE status IN ('pending','in_progress')")
    anomalies_24h = await pool.fetchval(
        "SELECT COUNT(*) FROM agent_activity WHERE severity IN ('warning','critical') "
        "AND created_at > now() - interval '24 hours'")
    return (
        f"🌊 <b>Сеть станций Дальнего Востока</b>\n\n"
        f"🟢 Норма: <b>{counts['normal']}</b>\n"
        f"🟡 Внимание: <b>{counts['warning']}</b>\n"
        f"🔴 Критично: <b>{counts['critical']}</b>\n"
        f"⚫ Офлайн: <b>{counts['offline']}</b>\n"
        f"─────────────────\n"
        f"📊 Всего станций: {counts['total']}\n"
        f"✍ Заявок на подписи: <b>{open_req}</b>\n"
        f"⚠️ Событий за 24ч: <b>{anomalies_24h}</b>"
    )


async def _cmd_summary(chat_id: int, pool) -> str:
    if not pool:
        return "⚠️ БД недоступна"

    stations = await pool.fetch("""
        SELECT s.code, s.name, s.status,
               r.sst, r.wind_speed, r.wave_height, r.observed_at
        FROM stations s
        LEFT JOIN LATERAL (
            SELECT sst, wind_speed, wave_height, observed_at
            FROM readings WHERE station_id = s.id ORDER BY observed_at DESC LIMIT 1
        ) r ON true
        ORDER BY s.code
        LIMIT 15
    """)

    anomaly_count = await pool.fetchval(
        "SELECT COUNT(*) FROM agent_activity WHERE severity = 'critical' "
        "AND created_at > now() - interval '24 hours'") or 0
    pending_count = await pool.fetchval(
        "SELECT COUNT(*) FROM requests WHERE status = 'pending'") or 0

    station_list = [dict(s) for s in stations]

    # Попытка создать сводку через GigaChat
    try:
        from services.gigachat import summarize_daily_report
        summary = await summarize_daily_report(station_list, anomaly_count, pending_count)
        if summary:
            return (
                f"📋 <b>Ежедневная сводка AI Serendipity</b>\n"
                f"<i>{_today()}</i>\n\n"
                f"{summary}\n\n"
                f"<i>Анализ: GigaChat × AI Serendipity</i>"
            )
    except Exception as e:
        logger.warning("GigaChat summary failed: %s", e)

    # Резервный вариант: обычная сводка
    lines = []
    warning_stations = [s for s in station_list if s["status"] in ("warning", "critical")]
    for s in warning_stations[:5]:
        icon = "🔴" if s["status"] == "critical" else "🟡"
        lines.append(f"{icon} {s['name']}: ТПО {_fmt(s.get('sst'))}°C")
    normal_count = sum(1 for s in station_list if s["status"] == "normal")

    return (
        f"📋 <b>Сводка {_today()}</b>\n\n"
        f"🟢 В норме: {normal_count} станций\n"
        f"⚠️ Требуют внимания: {len(warning_stations)}\n"
        + ("\n".join(lines) + "\n" if lines else "")
        + f"\n✍ Заявок на подписи: {pending_count}"
        + f"\n🔔 Критических событий за 24ч: {anomaly_count}"
    )


async def _cmd_station(chat_id: int, code: str | None, pool) -> str:
    if not code:
        return "Укажите код: /station VVO"
    if not pool:
        return "⚠️ БД недоступна"

    station = await pool.fetchrow("SELECT * FROM stations WHERE code = $1", code.upper())
    if not station:
        return f"Станция <b>{code}</b> не найдена. Коды: VVO, PKC, OKH, MGD и др."

    readings = await pool.fetch(
        "SELECT * FROM readings WHERE station_id = $1 ORDER BY observed_at DESC LIMIT 5",
        station["id"])

    # Получение данных ближайшего узла GFS как «дополнение наблюдателя»
    gfs_note = await _get_gfs_node_data(station)

    if not readings:
        base = (
            f"📍 <b>{station['name']}</b> ({code})\n"
            f"Нет данных наблюдений\n"
            + (f"\n{gfs_note}" if gfs_note else "")
        )
        return base

    r = readings[0]
    status_icon = {"normal": "🟢", "warning": "🟡", "critical": "🔴", "offline": "⚫"}.get(
        r["status"], "⚪")

    base = (
        f"📍 <b>{station['name']}</b> ({code})\n"
        f"{status_icon} Статус: {r['status']}\n\n"
        f"🌡 Воздух: <b>{_fmt(r['temp_air'])}°C</b>\n"
        f"🌊 ТПО: <b>{_fmt(r['sst'])}°C</b>\n"
        f"💨 Ветер: <b>{_fmt(r['wind_speed'])} м/с</b>\n"
        f"🌊 Волны: <b>{_fmt(r['wave_height'])} м</b>\n"
        f"🔵 Давление: {_fmt(r['pressure'])} гПа\n"
    )
    if gfs_note:
        base += f"\n{gfs_note}\n"

    # Анализ GigaChat
    try:
        from services.gigachat import analyze_station_data
        readings_list = [{"sst": r["sst"], "wind_speed": r["wind_speed"],
                          "wave_height": r["wave_height"], "status": r["status"]}
                         for r in readings]
        analysis = await analyze_station_data(station["name"], readings_list)
        if analysis:
            base += f"\n💡 <i>{analysis}</i>"
    except Exception as e:
        logger.warning("GigaChat station analysis failed: %s", e)

    return base


async def _cmd_forecast(chat_id: int, code: str | None, pool) -> str:
    if not code:
        return "Укажите код: /forecast VVO"
    if not pool:
        return "⚠️ БД недоступна"

    station = await pool.fetchrow("SELECT * FROM stations WHERE code = $1", code.upper())
    if not station:
        return f"Станция <b>{code}</b> не найдена"

    readings = await pool.fetch(
        "SELECT observed_at, sst FROM readings WHERE station_id = $1 "
        "AND sst IS NOT NULL ORDER BY observed_at DESC LIMIT 48",
        station["id"])

    readings_list = [{"observed_at": str(r["observed_at"]), "sst": float(r["sst"])}
                     for r in readings]

    # Прогноз Prophet (по умолчанию)
    from services.prophet_forecast import get_station_forecast_prophet
    fc = await get_station_forecast_prophet(code.upper(), readings_list, periods=6)

    hours_labels = ["сейчас", "+6ч", "+12ч", "+24ч", "+48ч", "+72ч"][:len(fc["forecast"])]
    forecast_lines = "\n".join(
        f"  {lbl}: <b>{v}°C</b>"
        for lbl, v in zip(hours_labels, fc["forecast"])
    )

    trend_arrow = "↗" if fc["trend"] > 0.05 else ("↘" if fc["trend"] < -0.05 else "→")
    anomaly_warn = (
        f"\n⚠️ Обнаружено аномалий за 24ч: {fc['n_anomalies_24h']}"
        if fc.get("n_anomalies_24h", 0) > 0 else ""
    )

    # Примечание о доступности AI Serendipity (TimeGPT) в веб-интерфейсе
    serendipity_note = ""
    if fc["method"] == "prophet":
        serendipity_note = "\n<i>🤖 AI Serendipity (TimeGPT) доступен в веб-интерфейсе</i>"

    return (
        f"🔮 <b>Прогноз ТПО — {station['name']}</b>\n"
        f"Метод: <b>{fc['method'].replace('_', ' ').title()}</b> "
        f"| Тренд: {trend_arrow} {abs(fc['trend']):.2f}°C/сут\n\n"
        f"{forecast_lines}"
        f"{anomaly_warn}"
        f"{serendipity_note}"
    )


async def _cmd_pending(chat_id: int, pool) -> str:
    """Неподписанные заявки — для supervisors."""
    if not pool:
        return "⚠️ БД недоступна"

    rows = await pool.fetch("""
        SELECT r.id, r.title, r.priority, r.created_at,
               u.full_name as author, s.name as station_name
        FROM requests r
        LEFT JOIN users u ON u.id = r.created_by
        LEFT JOIN stations s ON s.id = r.station_id
        WHERE r.status = 'pending'
        ORDER BY r.created_at DESC
        LIMIT 10
    """)

    if not rows:
        return "✅ Нет заявок, ожидающих подписи"

    lines = []
    for r in rows:
        priority_icon = {"urgent": "🔴", "high": "🟠", "normal": "🟡", "low": "🔵"}.get(
            r["priority"], "⚪")
        date_str = r["created_at"].strftime("%d.%m %H:%M") if r["created_at"] else ""
        lines.append(
            f"{priority_icon} <b>{r['title'][:50]}</b>\n"
            f"   📍 {r['station_name'] or '—'} | ✍ {r['author'] or '—'} | {date_str}"
        )

    return (
        f"📋 <b>Заявки на подписи ({len(rows)})</b>\n\n"
        + "\n\n".join(lines)
        + "\n\n<i>Для подписи перейдите в веб-интерфейс → Заявки</i>"
    )


async def _cmd_events(chat_id: int, pool) -> str:
    """Знаменательные события и аномалии."""
    if not pool:
        return "⚠️ БД недоступна"

    events = await pool.fetch("""
        SELECT agent_name, event_type, severity, title, created_at
        FROM agent_activity
        WHERE created_at > now() - interval '48 hours'
        ORDER BY created_at DESC
        LIMIT 12
    """)

    if not events:
        return "📭 Событий за последние 48ч не зафиксировано"

    lines = []
    for e in events:
        icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(e["severity"], "⚪")
        date_str = e["created_at"].strftime("%d.%m %H:%M") if e["created_at"] else ""
        lines.append(f"{icon} <b>{e['title'][:60]}</b>\n   <i>{e['agent_name']} · {date_str}</i>")

    return (
        f"🔔 <b>События за 48ч</b>\n\n"
        + "\n\n".join(lines)
    )


async def _cmd_free_text(chat_id: int, text: str, pool) -> str:
    """Обработка произвольного текста ИИ-ассистентом с контекстом из системы мониторинга."""
    # Сбор актуального контекста для ИИ
    context_parts = []
    if pool:
        try:
            counts = await pool.fetchrow("""
                SELECT COUNT(*) FILTER (WHERE status = 'normal') AS normal,
                       COUNT(*) FILTER (WHERE status = 'warning') AS warning,
                       COUNT(*) FILTER (WHERE status = 'critical') AS critical,
                       COUNT(*) FILTER (WHERE status = 'offline') AS offline,
                       COUNT(*) AS total
                FROM stations
            """)
            if counts:
                context_parts.append(
                    f"Станции: всего {counts['total']} "
                    f"(норма: {counts['normal']}, внимание: {counts['warning']}, "
                    f"критично: {counts['critical']}, офлайн: {counts['offline']})"
                )
        except Exception:
            pass
        try:
            recent = await pool.fetch("""
                SELECT s.name, s.code, r.sst, r.wind_speed, r.wave_height, r.status
                FROM stations s
                LEFT JOIN LATERAL (
                    SELECT sst, wind_speed, wave_height, status
                    FROM readings WHERE station_id = s.id ORDER BY observed_at DESC LIMIT 1
                ) r ON true
                WHERE r.status IN ('warning', 'critical')
                LIMIT 5
            """)
            if recent:
                alerts = "; ".join(
                    f"{r['name']} ({r['code']}): ТПО {_fmt(r['sst'])}°C, ветер {_fmt(r['wind_speed'])} м/с ({r['status']})"
                    for r in recent
                )
                context_parts.append(f"Станции с аномалиями: {alerts}")
        except Exception:
            pass
        try:
            pending = await pool.fetch("""
                SELECT r.id, r.title, r.priority, r.status, r.created_at,
                       u.full_name as author, s.name as station_name
                FROM requests r
                LEFT JOIN users u ON u.id = r.created_by
                LEFT JOIN stations s ON s.id = r.station_id
                WHERE r.status IN ('pending', 'in_progress')
                ORDER BY r.created_at DESC
                LIMIT 15
            """)
            if pending:
                req_lines = []
                for r in pending:
                    date_str = r["created_at"].strftime("%d.%m.%Y %H:%M") if r["created_at"] else ""
                    req_lines.append(
                        f"  #{r['id']} \"{r['title']}\" | приоритет: {r['priority']} | "
                        f"статус: {r['status']} | станция: {r['station_name'] or '—'} | "
                        f"автор: {r['author'] or '—'} | дата: {date_str}"
                    )
                context_parts.append(f"Заявки/документы (ожидают подписи или в работе):\n" + "\n".join(req_lines))
            else:
                context_parts.append("Неподписанных заявок/документов нет.")
        except Exception:
            pass
        # Дежурства — сейчас и на ближайшие 3 дня
        try:
            duty_now = await pool.fetch("""
                SELECT u.full_name, p.position, a.role_on_duty,
                       s.code as station_code, s.name as station_name,
                       a.shift_start, a.shift_end
                FROM assignments a
                JOIN personnel p ON p.id = a.personnel_id
                JOIN users u ON u.id = p.user_id
                JOIN stations s ON s.id = a.station_id
                WHERE a.shift_start <= now() AND a.shift_end >= now() 
                   OR a.shift_start::date = current_date
                ORDER BY s.code
            """)
            duty_upcoming = await pool.fetch("""
                SELECT u.full_name, p.position, a.role_on_duty,
                       s.code as station_code, s.name as station_name,
                       a.shift_start, a.shift_end
                FROM assignments a
                JOIN personnel p ON p.id = a.personnel_id
                JOIN users u ON u.id = p.user_id
                JOIN stations s ON s.id = a.station_id
                WHERE a.shift_start > now() AND a.shift_start <= now() + interval '3 days'
                  AND a.shift_start::date > current_date
                ORDER BY a.shift_start, s.code
                LIMIT 30
            """)
            if duty_now:
                lines = []
                for d in duty_now:
                    lines.append(f"  {d['full_name']} — {d['station_name']} ({d['station_code']}), "
                                 f"роль: {d['role_on_duty'] or d['position']}, "
                                 f"с {d['shift_start'].strftime('%H:%M')} до {d['shift_end'].strftime('%d.%m %H:%M')}")
                context_parts.append("Дежурят сегодня (или прямо сейчас):\n" + "\n".join(lines))
            else:
                context_parts.append("Дежурят сегодня: никого (смен нет)")
            if duty_upcoming:
                lines = []
                for d in duty_upcoming:
                    lines.append(f"  {d['full_name']} — {d['station_name']} ({d['station_code']}), "
                                 f"{d['shift_start'].strftime('%d.%m %H:%M')}–{d['shift_end'].strftime('%H:%M')}, "
                                 f"роль: {d['role_on_duty'] or d['position']}")
                context_parts.append("Ближайшие дежурства (3 дня):\n" + "\n".join(lines))
        except Exception:
            pass
        try:
            events = await pool.fetch("""
                SELECT agent_name, event_type, severity, title, created_at
                FROM agent_activity
                WHERE created_at > now() - interval '48 hours'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            if events:
                ev_lines = []
                for e in events:
                    date_str = e["created_at"].strftime("%d.%m %H:%M") if e["created_at"] else ""
                    ev_lines.append(f"  [{e['severity']}] {e['title']} ({e['agent_name']}, {date_str})")
                context_parts.append(f"События за 48ч:\n" + "\n".join(ev_lines))
        except Exception:
            pass
        # Прогнозы Prophet по станциям с данными
        try:
            from services.prophet_forecast import get_station_forecast_prophet
            forecast_stations = await pool.fetch("""
                SELECT s.code, s.name,
                       array_agg(json_build_object('observed_at', r.observed_at::text, 'sst', r.sst)
                                 ORDER BY r.observed_at DESC) AS readings_arr
                FROM stations s
                JOIN LATERAL (
                    SELECT observed_at, sst FROM readings
                    WHERE station_id = s.id AND sst IS NOT NULL
                    ORDER BY observed_at DESC LIMIT 48
                ) r ON true
                GROUP BY s.code, s.name
                LIMIT 8
            """)
            fc_lines = []
            for fs in forecast_stations:
                import json as _json
                readings_list = [_json.loads(r) if isinstance(r, str) else r for r in fs["readings_arr"]]
                fc = await get_station_forecast_prophet(fs["code"], readings_list, periods=3)
                trend_word = "рост" if fc["trend"] > 0.05 else ("снижение" if fc["trend"] < -0.05 else "стабильно")
                vals = ", ".join(f"{v}°C" for v in fc["forecast"][:3])
                anom = f", аномалий: {fc['n_anomalies_24h']}" if fc.get("n_anomalies_24h", 0) > 0 else ""
                fc_lines.append(f"  {fs['name']} ({fs['code']}): прогноз [{vals}], тренд: {trend_word}{anom}")
            if fc_lines:
                context_parts.append("Прогнозы ТПО (Prophet, ближайшие 6-18ч):\n" + "\n".join(fc_lines))
        except Exception:
            pass

    context = "\n".join(context_parts) if context_parts else "Данные системы недоступны."

    try:
        from services.gigachat import chat as ai_chat
        system = (
            "Ты — ИИ-ассистент системы мониторинга "
            "прибрежных морских станций Дальнего Востока России. "
            "Ты в курсе ВСЕХ процессов: станции, заявки, документы, события, прогнозы, дежурства.\n\n"
            "Ты имеешь доступ ко ВСЕМ данным дашборда и отвечаешь на ЛЮБЫЕ вопросы:\n"
            "- Станции: статусы, показания (ТПО, ветер, волны, давление), аномалии\n"
            "- Дежурства: кто сейчас на дежурстве, кто заступает завтра, графики смен\n"
            "- Заявки и документы: неподписанные, в работе, приоритеты, авторы\n"
            "- События и аномалии: критические, предупреждения за последние 48ч\n"
            "- Прогнозы ТПО: Prophet, GFS, нейросетевая коррекция\n"
            "- Персонал: должности, телефоны, привязка к станциям\n"
            "- Океанология, метеорология, климатические нормы Северной Пацифики\n"
            "- Станции: Владивосток, Находка, Охотск, Магадан, Петропавловск-Камчатский, Поронайск и др.\n\n"
            f"АКТУАЛЬНЫЕ ДАННЫЕ СИСТЕМЫ:\n{context}\n\n"
            "ПРАВИЛА ОТВЕТА:\n"
            "- НИКОГДА не используй Markdown-разметку (**, ##, ```, и т.д.) — пиши ПРОСТЫМ ТЕКСТОМ\n"
            "- Для структуры используй тире (-), нумерацию (1. 2. 3.) и переносы строк\n"
            "- ПИШИ ТОЛЬКО РЕЗЮМЕ, а не весь отчет. Будь краток (3-5 предложений).\n"
            "- Отвечай на русском, лаконично и профессионально\n"
            "- Когда говоришь о прогнозах и ожидаемых событиях, начинай с фразы "
            "\"Ассистент говорит, что ожидается...\" или \"Ассистент прогнозирует...\"\n"
            "- Используй актуальные данные из контекста для ответов\n"
            "- Если спрашивают про дежурства — отвечай кто сейчас дежурит, кто заступает\n"
            "- Если спрашивают про заявки, документы, подписи — отвечай на основе данных\n"
            "- Если спрашивают про станцию — используй актуальные показания\n"
            "- Ты знаешь всё о работе сети: кто дежурит, кто подал заявку, какие станции в норме, "
            "какие прогнозы, какие аномалии зафиксированы\n"
            "- Предлагай команды бота: /station, /forecast, /pending, /events, /summary\n"
            "- Анализируй данные как опытный специалист-синоптик"
        )
        reply = await ai_chat(system, text, max_tokens=800)
        if reply:
            return reply
    except Exception as e:
        logger.warning("AI chat failed: %s", e)

    import re
    summary_text = await _cmd_summary(chat_id, pool)
    summary_text_plain = re.sub(r'<[^>]+>', '', summary_text).replace('&lt;', '<').replace('&gt;', '>')
    return (
        "🤖 К сожалению, ИИ-ассистент сейчас недоступен.\n\n"
        f"{summary_text_plain}\n\n"
        "Доступные команды:\n"
        "/status — сводка по сети\n"
        "/station VVO — данные станции\n"
        "/forecast VVO — прогноз ТПО\n"
        "/summary — ежедневная сводка\n"
        "/events — аномалии и события"
    )


async def _get_gfs_node_data(station) -> str | None:
    """Получает данные ближайшего узла сетки GFS для станции (представляются как дополнение)."""
    try:
        from services.gee_gfs import get_fetcher
        fetcher = get_fetcher()
        vals = fetcher.extract_station_values([dict(station)], hour=0)
        if vals:
            v = vals[0]
            sst = v.get("sst")
            wind = v.get("wind_speed")
            return (
                f"📡 <i>GFS-прогноз узла: ТПО {_fmt(sst)}°C, ветер {_fmt(wind)} м/с</i>"
            )
    except Exception:
        pass
    return None


# ── Рассылка ежедневной сводки ────────────────────────────────────────────────

async def send_daily_summary(pool):
    """Вызывается планировщиком раз в день. Отправляет сводку всем супервайзерам."""
    if not pool or not SUPERVISOR_CHAT_IDS:
        # Попытка загрузить ID чатов супервайзеров из БД
        if pool:
            rows = await pool.fetch(
                "SELECT telegram_chat_id FROM users WHERE role = 'supervisor' "
                "AND telegram_chat_id IS NOT NULL")
            for r in rows:
                SUPERVISOR_CHAT_IDS.add(r["telegram_chat_id"])
        if not SUPERVISOR_CHAT_IDS:
            logger.info("Daily summary: no supervisor chat IDs registered")
            return

    summary = await _cmd_summary(None, pool)
    for chat_id in list(SUPERVISOR_CHAT_IDS):
        await send_message(chat_id, "🌅 <b>Ежедневная сводка</b>\n\n" + summary.replace(
            "📋 <b>Ежедневная сводка AI Serendipity</b>\n", ""))
    logger.info("Daily summary sent to %d supervisors", len(SUPERVISOR_CHAT_IDS))


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _fmt(val, decimals: int = 1) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.{decimals}f}".replace(".", ",")
    except Exception:
        return str(val)


def _today() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%d.%m.%Y")
