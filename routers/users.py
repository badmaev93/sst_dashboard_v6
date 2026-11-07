from fastapi import APIRouter, Depends
import db
from auth import require_role
from models import AssignmentCreate

users_router = APIRouter(prefix="/api/monitoring/users", tags=["users"])

@users_router.get("/")
async def list_users(user=Depends(require_role("supervisor"))):
    rows = await db.pool.fetch("SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY id")
    return [dict(r) for r in rows]

@users_router.get("/personnel")
async def list_personnel(user=Depends(require_role("supervisor"))):
    rows = await db.pool.fetch("""
        SELECT p.*, u.full_name, u.role as user_role, s.name as station_name, s.code as station_code
        FROM personnel p
        LEFT JOIN users u ON u.id = p.user_id
        LEFT JOIN stations s ON s.id = p.station_id
        ORDER BY p.id
    """)
    return [dict(r) for r in rows]

@users_router.post("/assignments")
async def create_assignment(data: AssignmentCreate, user=Depends(require_role("supervisor"))):
    # Security: validate assignment input payload with AssignmentCreate to ensure correct datatypes and boundaries
    row = await db.pool.fetchrow("""
        INSERT INTO assignments (personnel_id, station_id, shift_start, shift_end, role_on_duty)
        VALUES ($1, $2, $3, $4, $5) RETURNING id
    """, data.personnel_id, data.station_id, data.shift_start, data.shift_end, data.role_on_duty or "Наблюдатель")
    return {"id": row["id"]}
