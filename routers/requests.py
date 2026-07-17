from fastapi import APIRouter, HTTPException, Depends, Query
import db
from auth import get_current_user, require_role
from models import RequestCreate

requests_router = APIRouter(prefix="/api/monitoring/requests", tags=["requests"])

@requests_router.get("/")
async def list_requests(status: str = None, req_type: str = None, station_id: int = None):
    conditions, params = [], []
    idx = 1
    if status:
        conditions.append(f"status = ${idx}")
        params.append(status); idx += 1
    if req_type:
        conditions.append(f"req_type = ${idx}")
        params.append(req_type); idx += 1
    if station_id:
        conditions.append(f"station_id = ${idx}")
        params.append(station_id); idx += 1
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await db.pool.fetch(f"""
        SELECT r.*, u1.full_name as author_name, u2.full_name as assignee_name, s.name as station_name
        FROM requests r
        LEFT JOIN users u1 ON u1.id = r.created_by
        LEFT JOIN users u2 ON u2.id = r.assigned_to
        LEFT JOIN stations s ON s.id = r.station_id
        {where} ORDER BY r.created_at DESC
    """, *params)
    return [dict(r) for r in rows]

@requests_router.post("/")
async def create_request(data: RequestCreate, user=Depends(get_current_user)):
    row = await db.pool.fetchrow("""
        INSERT INTO requests (station_id, created_by, assigned_to, title, description, req_type, priority)
        VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id
    """, data.station_id, user["id"], data.assigned_to, data.title, data.description, data.req_type, data.priority)
    return {"id": row["id"]}

@requests_router.put("/{req_id}")
async def update_request(req_id: int, data: dict, user=Depends(get_current_user)):
    existing = await db.pool.fetchrow("SELECT * FROM requests WHERE id = $1", req_id)
    if not existing:
        raise HTTPException(404, "Request not found")
    await db.pool.execute("""
        UPDATE requests SET title=COALESCE($1,title), description=COALESCE($2,description),
            status=COALESCE($3,status), priority=COALESCE($4,priority) WHERE id=$5
    """, data.get("title"), data.get("description"), data.get("status"), data.get("priority"), req_id)
    return {"ok": True}

@requests_router.post("/{req_id}/sign")
async def sign_request(req_id: int, action: str = Query(..., pattern="^(approve|reject)$"),
                       user=Depends(require_role("supervisor"))):
    existing = await db.pool.fetchrow("SELECT * FROM requests WHERE id = $1", req_id)
    if not existing:
        raise HTTPException(404, "Request not found")
    new_status = "signed" if action == "approve" else "rejected"
    await db.pool.execute(
        "UPDATE requests SET status = $1, signed_at = now() WHERE id = $2",
        new_status, req_id)
    return {"ok": True, "status": new_status}
