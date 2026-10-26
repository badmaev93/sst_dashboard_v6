from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query

import db
from auth import get_current_user, require_role

schedule_router = APIRouter(prefix="/api/monitoring/schedule", tags=["schedule"])


def _parse_date(s: str) -> datetime:
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@schedule_router.get("/")
async def get_schedule(
    station_id: int = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    user=Depends(get_current_user),
):
    conditions = []
    params = []
    idx = 1

    if station_id:
        conditions.append(f"a.station_id = ${idx}")
        params.append(station_id)
        idx += 1

    if date_from:
        conditions.append(f"a.shift_end >= ${idx}")
        params.append(_parse_date(date_from))
        idx += 1

    if date_to:
        conditions.append(f"a.shift_start <= ${idx}")
        params.append(_parse_date(date_to))
        idx += 1

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await db.pool.fetch(f"""
        SELECT a.id, a.shift_start, a.shift_end, a.role_on_duty,
               p.id as personnel_id, p.position,
               u.full_name, u.role as user_role,
               s.id as station_id, s.code as station_code, s.name as station_name
        FROM assignments a
        JOIN personnel p ON p.id = a.personnel_id
        JOIN users u ON u.id = p.user_id
        JOIN stations s ON s.id = a.station_id
        {where}
        ORDER BY a.shift_start
    """, *params)
    return [dict(r) for r in rows]


@schedule_router.get("/stations")
async def get_stations_for_schedule(user=Depends(get_current_user)):
    rows = await db.pool.fetch("SELECT id, code, name, region FROM stations ORDER BY code")
    return [dict(r) for r in rows]


@schedule_router.get("/personnel")
async def get_personnel_for_schedule(user=Depends(get_current_user)):
    rows = await db.pool.fetch("""
        SELECT p.id, p.position, p.station_id,
               u.full_name, u.role as user_role,
               s.code as station_code, s.name as station_name
        FROM personnel p
        JOIN users u ON u.id = p.user_id
        LEFT JOIN stations s ON s.id = p.station_id
        ORDER BY u.full_name
    """)
    return [dict(r) for r in rows]


@schedule_router.post("/")
async def create_assignment(data: dict, user=Depends(require_role("supervisor"))):
    row = await db.pool.fetchrow("""
        INSERT INTO assignments (personnel_id, station_id, shift_start, shift_end, role_on_duty)
        VALUES ($1, $2, $3, $4, $5) RETURNING id
    """, data["personnel_id"], data["station_id"],
        _parse_date(data["shift_start"]), _parse_date(data["shift_end"]),
        data.get("role_on_duty", "Наблюдатель"))
    return {"id": row["id"]}


@schedule_router.put("/{assignment_id}")
async def update_assignment(assignment_id: int, data: dict, user=Depends(require_role("supervisor"))):
    await db.pool.execute("""
        UPDATE assignments SET
            personnel_id = COALESCE($2, personnel_id),
            station_id = COALESCE($3, station_id),
            shift_start = COALESCE($4::timestamptz, shift_start),
            shift_end = COALESCE($5::timestamptz, shift_end),
            role_on_duty = COALESCE($6, role_on_duty)
        WHERE id = $1
    """, assignment_id,
        data.get("personnel_id"), data.get("station_id"),
        data.get("shift_start"), data.get("shift_end"),
        data.get("role_on_duty"))
    return {"ok": True}


@schedule_router.delete("/{assignment_id}")
async def delete_assignment(assignment_id: int, user=Depends(require_role("supervisor"))):
    await db.pool.execute("DELETE FROM assignments WHERE id = $1", assignment_id)
    return {"ok": True}


@schedule_router.get("/today")
async def get_today_schedule(user=Depends(get_current_user)):
    now = datetime.now(UTC)
    rows = await db.pool.fetch("""
        SELECT a.id, a.shift_start, a.shift_end, a.role_on_duty,
               u.full_name, p.position,
               s.code as station_code, s.name as station_name
        FROM assignments a
        JOIN personnel p ON p.id = a.personnel_id
        JOIN users u ON u.id = p.user_id
        JOIN stations s ON s.id = a.station_id
        WHERE a.shift_start <= $1 AND a.shift_end >= $1
        ORDER BY s.code
    """, now)
    return [dict(r) for r in rows]


@schedule_router.get("/upcoming")
async def get_upcoming_schedule(days: int = Query(7), user=Depends(get_current_user)):
    now = datetime.now(UTC)
    end = now + timedelta(days=days)
    rows = await db.pool.fetch("""
        SELECT a.id, a.shift_start, a.shift_end, a.role_on_duty,
               u.full_name, p.position,
               s.code as station_code, s.name as station_name
        FROM assignments a
        JOIN personnel p ON p.id = a.personnel_id
        JOIN users u ON u.id = p.user_id
        JOIN stations s ON s.id = a.station_id
        WHERE a.shift_start >= $1 AND a.shift_start <= $2
        ORDER BY a.shift_start, s.code
    """, now, end)
    return [dict(r) for r in rows]
