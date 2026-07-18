from fastapi import APIRouter, Depends
import db
from auth import get_current_user, require_role
from models import EquipmentCheckCreate

equipment_router = APIRouter(prefix="/api/monitoring/equipment", tags=["equipment"])

@equipment_router.get("/checks")
async def list_checks(station_id: int = None, user=Depends(get_current_user)):
    if station_id:
        rows = await db.pool.fetch("""
            SELECT ec.*, u.full_name as engineer_name, s.name as station_name
            FROM equipment_checks ec
            LEFT JOIN users u ON u.id = ec.checked_by
            LEFT JOIN stations s ON s.id = ec.station_id
            WHERE ec.station_id = $1 ORDER BY ec.checked_at DESC
        """, station_id)
    else:
        rows = await db.pool.fetch("""
            SELECT ec.*, u.full_name as engineer_name, s.name as station_name
            FROM equipment_checks ec
            LEFT JOIN users u ON u.id = ec.checked_by
            LEFT JOIN stations s ON s.id = ec.station_id
            ORDER BY ec.checked_at DESC LIMIT 100
        """)
    return [dict(r) for r in rows]

@equipment_router.post("/checks")
async def create_check(data: EquipmentCheckCreate, user=Depends(require_role("engineer", "supervisor"))):
    row = await db.pool.fetchrow("""
        INSERT INTO equipment_checks (station_id, checked_by, equipment, result, notes)
        VALUES ($1, $2, $3, $4, $5) RETURNING id
    """, data.station_id, user["id"], data.equipment, data.result, data.notes)
    return {"id": row["id"]}
