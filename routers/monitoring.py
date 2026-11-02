from fastapi import APIRouter, Query, Depends
from datetime import datetime, timezone
import asyncio
import db
import logging
from auth import get_current_user, require_role

logger = logging.getLogger(__name__)

monitoring_router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

@monitoring_router.get("/feed")
async def activity_feed(limit: int = Query(50, le=200), offset: int = 0,
                        severity: str = None, agent_name: str = None,
                        user=Depends(get_current_user)):
    conditions = []
    params = []
    idx = 1
    if severity:
        conditions.append(f"severity = ${idx}")
        params.append(severity)
        idx += 1
    if agent_name:
        conditions.append(f"agent_name = ${idx}")
        params.append(agent_name)
        idx += 1
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.extend([limit, offset])
    rows = await db.pool.fetch(f"""
        SELECT * FROM agent_activity {where}
        ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}
    """, *params)
    result = []
    for r in rows:
        d = dict(r)
        d["timestamp"] = d.get("created_at").isoformat() if d.get("created_at") else None
        result.append(d)
    return result

@monitoring_router.get("/dashboard/summary")
async def dashboard_summary(user=Depends(get_current_user)):
    # ⚡ Bolt: Execute independent queries concurrently to reduce dashboard latency
    counts_task = db.pool.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'normal') as normal,
            COUNT(*) FILTER (WHERE status = 'warning') as warning,
            COUNT(*) FILTER (WHERE status = 'critical') as critical,
            COUNT(*) FILTER (WHERE status = 'offline') as offline
        FROM stations
    """)
    open_req_task = db.pool.fetchval(
        "SELECT COUNT(*) FROM requests WHERE status IN ('pending','in_progress')")
    anomalies_task = db.pool.fetchval(
        "SELECT COUNT(*) FROM agent_activity WHERE severity = 'critical' AND created_at > now() - interval '7 days'")
    agents_task = db.pool.fetch("""
        SELECT DISTINCT ON (agent_name) agent_name, created_at as last_activity
        FROM agent_activity ORDER BY agent_name, created_at DESC
    """)
    avg_sst_task = db.pool.fetch("""
        SELECT date_trunc('day', observed_at) as day, AVG(sst) as avg_sst
        FROM readings WHERE observed_at > now() - interval '7 days' AND sst IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """)
    anomaly_days_task = db.pool.fetch("""
        SELECT date_trunc('day', created_at) as day, COUNT(*) as cnt
        FROM agent_activity WHERE severity = 'critical' AND created_at > now() - interval '30 days'
        GROUP BY 1 ORDER BY 1
    """)
    station_rows_task = db.pool.fetch("""
        SELECT s.id, s.code, s.name, s.region, s.lat, s.lon, s.status,
               r.sst, r.temp_air, r.wind_speed, r.wave_height, r.pressure, r.humidity,
               r.observed_at
        FROM stations s
        LEFT JOIN LATERAL (
            SELECT sst, temp_air, wind_speed, wave_height, pressure, humidity, observed_at
            FROM readings WHERE station_id = s.id ORDER BY observed_at DESC LIMIT 1
        ) r ON true
        ORDER BY s.id
    """)
    events_rows_task = db.pool.fetch("""
        SELECT agent_name, severity, title as message, created_at as timestamp
        FROM agent_activity
        WHERE created_at > now() - interval '48 hours'
        ORDER BY created_at DESC LIMIT 20
    """)

    counts, open_req, anomalies, agents, avg_sst, anomaly_days, station_rows, events_rows = await asyncio.gather(
        counts_task, open_req_task, anomalies_task, agents_task, avg_sst_task, anomaly_days_task, station_rows_task, events_rows_task
    )

    sc = dict(counts) if counts else {"normal":0,"warning":0,"critical":0,"offline":0}

    # Список станций с последними измерениями для кликабельных счетчиков статуса
    stations_list = []
    for row in station_rows:
        d = dict(row)
        lr = {k: d.pop(k) for k in ["sst","temp_air","wind_speed","wave_height","pressure","humidity","observed_at"]}
        d["latest_reading"] = {k: (v.isoformat() if hasattr(v,"isoformat") else v) for k,v in lr.items()}
        stations_list.append(d)

    # События станций из недавней активности агентов
    station_events = [{"station_name": r["agent_name"],
                       "severity": r["severity"], "message": r["message"],
                       "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None}
                      for r in events_rows]

    # График ТПО (7 дней)
    sst_labels = [r["day"].strftime("%d %b") for r in avg_sst]
    sst_data   = [round(float(r["avg_sst"]), 1) for r in avg_sst]

    # График аномалий (30 дней)
    from datetime import date, timedelta
    all_days = [(date.today() - timedelta(days=29-i)) for i in range(30)]
    anom_map = {r["day"].date(): int(r["cnt"]) for r in anomaly_days}
    anom_labels = [d.strftime("%d %b") for d in all_days]
    anom_data   = [anom_map.get(d, 0) for d in all_days]

    return {
        "stations_online":   sc.get("normal", 0),
        "stations_warning":  sc.get("warning", 0),
        "stations_critical": sc.get("critical", 0),
        "stations_offline":  sc.get("offline", 0),
        "station_counts": sc,
        "stations": stations_list,
        "station_events": station_events,
        "open_requests": open_req or 0,
        "recent_anomalies": anomalies or 0,
        "agents": [{"name": a["agent_name"], "last_activity": a["last_activity"].isoformat() if a["last_activity"] else None, "active": True} for a in agents],
        "sst_chart": {"labels": sst_labels, "data": sst_data} if sst_data else None,
        "anomaly_chart": {"labels": anom_labels, "data": anom_data},
    }


## Примечание: эндпоинт /stations находится в routers/stations.py, не дублируется здесь


@monitoring_router.post("/actions/{action}")
async def run_action(action: str, user=Depends(require_role("supervisor"))):
    now = datetime.now(timezone.utc)
    if action == "digest":
        stations = await db.pool.fetch("""
            SELECT s.name, s.status, r.sst
            FROM stations s
            LEFT JOIN LATERAL (
                SELECT sst FROM readings WHERE station_id = s.id ORDER BY observed_at DESC LIMIT 1
            ) r ON true ORDER BY s.name
        """)
        online = sum(1 for s in stations if s["status"] == "normal")
        warn = sum(1 for s in stations if s["status"] == "warning")
        crit = sum(1 for s in stations if s["status"] == "critical")
        sst_vals = [float(s["sst"]) for s in stations if s["sst"] is not None]
        avg_sst = round(sum(sst_vals) / len(sst_vals), 1) if sst_vals else None

        title = f"Дайджест сети: {online} онлайн, {warn} внимание, {crit} критично"
        body = f"Средняя ТПО: {avg_sst}°C. Всего станций: {len(stations)}."
        await db.pool.execute("""
            INSERT INTO agent_activity (agent_name, event_type, severity, title, body, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, "DigestBot", "digest", "info", title, body, now)
        return {"ok": True, "message": title}

    elif action == "anomaly_check":
        readings = await db.pool.fetch("""
            SELECT s.name, s.code, r.sst, r.wind_speed, r.wave_height
            FROM stations s
            LEFT JOIN LATERAL (
                SELECT sst, wind_speed, wave_height FROM readings WHERE station_id = s.id ORDER BY observed_at DESC LIMIT 1
            ) r ON true
        """)
        anomalies = []
        for r in readings:
            if r["wind_speed"] and float(r["wind_speed"]) > 15:
                anomalies.append(f"{r['name']}: ветер {r['wind_speed']} м/с")
            if r["wave_height"] and float(r["wave_height"]) > 3:
                anomalies.append(f"{r['name']}: волны {r['wave_height']} м")

        sev = "warning" if anomalies else "info"
        title = f"Проверка аномалий: найдено {len(anomalies)}" if anomalies else "Проверка аномалий: всё в норме"
        body = "\n".join(anomalies[:10]) if anomalies else "Все показатели в пределах нормы."
        await db.pool.execute("""
            INSERT INTO agent_activity (agent_name, event_type, severity, title, body, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, "AnomalyChecker", "anomaly_check", sev, title, body, now)
        return {"ok": True, "message": title, "anomalies": len(anomalies)}
