from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import date as _date, datetime as _dt
import db
from auth import get_current_user, require_role
from models import CalendarEventCreate

def _parse_date(s):
    if not s: return None
    if isinstance(s, (_date, _dt)): return s
    try: return _dt.fromisoformat(s)
    except: pass
    try: return _date.fromisoformat(s)
    except: return s

calendar_router = APIRouter(prefix="/api/monitoring/calendar", tags=["calendar"])

@calendar_router.get("/events")
async def list_events(start: str = None, end: str = None, station_id: int = None, user=Depends(get_current_user)):
    conditions, params = [], []
    idx = 1
    if start:
        conditions.append(f"starts_at >= ${idx}::timestamptz")
        params.append(_parse_date(start)); idx += 1
    if end:
        conditions.append(f"ends_at <= ${idx}::timestamptz")
        params.append(_parse_date(end)); idx += 1
    if station_id:
        conditions.append(f"station_id = ${idx}")
        params.append(station_id); idx += 1
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await db.pool.fetch(f"SELECT * FROM calendar_events {where} ORDER BY starts_at", *params)
    return [dict(r) for r in rows]

@calendar_router.post("/events")
async def create_event(data: CalendarEventCreate, user=Depends(require_role("engineer", "supervisor"))):
    row = await db.pool.fetchrow("""
        INSERT INTO calendar_events (title, description, event_type, station_id, created_by, starts_at, ends_at, all_day, color)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
    """, data.title, data.description, data.event_type, data.station_id, user["id"],
        data.starts_at, data.ends_at, data.all_day, data.color)
    return {"id": row["id"]}

@calendar_router.put("/events/{event_id}")
async def update_event(event_id: int, data: CalendarEventCreate, user=Depends(get_current_user)):
    existing = await db.pool.fetchrow("SELECT * FROM calendar_events WHERE id = $1", event_id)
    if not existing:
        raise HTTPException(404, "Event not found")
    if user["role"] != "supervisor" and existing["created_by"] != user["id"]:
        raise HTTPException(403, "Not authorized to update this event")

    await db.pool.execute("""
        UPDATE calendar_events SET title=$1, description=$2, event_type=$3, station_id=$4,
            starts_at=$5, ends_at=$6, all_day=$7, color=$8 WHERE id=$9
    """, data.title, data.description, data.event_type, data.station_id,
        data.starts_at, data.ends_at, data.all_day, data.color, event_id)
    return {"ok": True}

@calendar_router.delete("/events/{event_id}")
async def delete_event(event_id: int, user=Depends(require_role("supervisor"))):
    await db.pool.execute("DELETE FROM calendar_events WHERE id = $1", event_id)
    return {"ok": True}


# ── Задачи ──────────────────────────────────────────

@calendar_router.get("/tasks")
async def list_tasks(date: str = None, user_id: int = None, user=Depends(get_current_user)):
    conditions, params = [], []
    idx = 1
    if date:
        conditions.append(f"due_date::date = ${idx}::date")
        params.append(_parse_date(date)); idx += 1
    if user_id:
        conditions.append(f"assigned_to = ${idx}")
        params.append(user_id); idx += 1
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await db.pool.fetch(
        f"SELECT * FROM tasks {where} ORDER BY completed ASC, "
        f"CASE priority WHEN 'P1' THEN 0 WHEN 'P2' THEN 1 WHEN 'P3' THEN 2 END, created_at DESC",
        *params
    )
    return [dict(r) for r in rows]

@calendar_router.post("/tasks")
async def create_task(data: dict, user=Depends(get_current_user)):
    row = await db.pool.fetchrow("""
        INSERT INTO tasks (title, description, priority, estimated_minutes, due_date, station_id, assigned_to)
        VALUES ($1, $2, $3, $4, $5::timestamptz, $6, $7) RETURNING id
    """,
        data.get("title"),
        data.get("description"),
        data.get("priority", "P2"),
        data.get("estimated_minutes"),
        data.get("due_date"),
        data.get("station_id"),
        user["id"]
    )
    return {"id": row["id"]}

@calendar_router.put("/tasks/{task_id}")
async def update_task(task_id: int, data: dict, user=Depends(get_current_user)):
    existing = await db.pool.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
    if not existing:
        raise HTTPException(404, "Task not found")
    if user["role"] != "supervisor" and existing["assigned_to"] != user["id"]:
        raise HTTPException(403, "Not authorized to update this task")

    sets, params = [], []
    idx = 1
    for field in ("title", "description", "priority", "estimated_minutes", "completed"):
        if field in data:
            sets.append(f"{field} = ${idx}")
            params.append(data[field]); idx += 1
    if "due_date" in data:
        sets.append(f"due_date = ${idx}::timestamptz")
        params.append(data["due_date"]); idx += 1
    if "station_id" in data:
        sets.append(f"station_id = ${idx}")
        params.append(data["station_id"]); idx += 1
    if not sets:
        raise HTTPException(400, "No fields to update")
    params.append(task_id)
    await db.pool.execute(
        f"UPDATE tasks SET {', '.join(sets)} WHERE id = ${idx}", *params
    )
    return {"ok": True}


# ── Блоки фокусировки ───────────────────────────────

@calendar_router.get("/focus-blocks")
async def list_focus_blocks(user_id: int = None, user=Depends(get_current_user)):
    if user_id:
        rows = await db.pool.fetch(
            "SELECT * FROM focus_blocks WHERE user_id = $1 ORDER BY start_time", user_id
        )
    else:
        rows = await db.pool.fetch("SELECT * FROM focus_blocks ORDER BY start_time")
    return [dict(r) for r in rows]

@calendar_router.post("/focus-blocks")
async def create_focus_block(data: dict, user=Depends(get_current_user)):
    row = await db.pool.fetchrow("""
        INSERT INTO focus_blocks (title, start_time, end_time, color, user_id, day_of_week, recurring)
        VALUES ($1, $2::time, $3::time, $4, $5, $6, $7) RETURNING id
    """,
        data.get("title"),
        data.get("start_time"),
        data.get("end_time"),
        data.get("color", "#3b82f6"),
        user["id"],
        data.get("day_of_week"),
        data.get("recurring", False)
    )
    return {"id": row["id"]}
