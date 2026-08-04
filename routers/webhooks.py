import json
import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request

import db
from config import AGENT_API_KEY
from models import AgentInsight

logger = logging.getLogger(__name__)
webhooks_router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

def _check_key(key: str = Header(None, alias="X-Agent-Key")):
    # Fail closed if either the header or the configured AGENT_API_KEY is missing/empty
    if not key or not AGENT_API_KEY:
        raise HTTPException(403, "Invalid agent key")
    # Timing-attack resistant constant-time comparison
    if not secrets.compare_digest(key, AGENT_API_KEY):
        raise HTTPException(403, "Invalid agent key")

@webhooks_router.post("/agent/insight")
async def agent_insight(data: AgentInsight, _=Depends(_check_key)):  # noqa: B008
    row = await db.pool.fetchrow("""
        INSERT INTO agent_activity (agent_name, event_type, severity, title, body, metadata)
        VALUES ($1, 'insight', $2, $3, $4, $5) RETURNING id
    """, data.agent_name, data.severity, data.title, data.body,
        json.dumps(data.metadata) if data.metadata else None)
    return {"id": row["id"], "status": "accepted"}

@webhooks_router.post("/agent/status")
async def agent_status(data: AgentInsight, _=Depends(_check_key)):  # noqa: B008
    row = await db.pool.fetchrow("""
        INSERT INTO agent_activity (agent_name, event_type, severity, title, body, metadata)
        VALUES ($1, 'status', $2, $3, $4, $5) RETURNING id
    """, data.agent_name, data.severity, data.title, data.body,
        json.dumps(data.metadata) if data.metadata else None)
    return {"id": row["id"], "status": "accepted"}

@webhooks_router.post("/agent/anomaly")
async def agent_anomaly(data: AgentInsight, _=Depends(_check_key)):  # noqa: B008
    row = await db.pool.fetchrow("""
        INSERT INTO agent_activity (agent_name, event_type, severity, title, body, metadata)
        VALUES ($1, 'anomaly', $2, $3, $4, $5) RETURNING id
    """, data.agent_name, data.severity, data.title, data.body,
        json.dumps(data.metadata) if data.metadata else None)
    if data.severity == "critical":
        try:
            from services.notification import notify_supervisors
            await notify_supervisors(db.pool, f"CRITICAL: {data.title}")
        except Exception as e:
            logger.warning("Failed to notify: %s", e)
    return {"id": row["id"], "status": "accepted"}

@webhooks_router.post("/telegram")
async def telegram_webhook(request: Request):
    body = await request.json()
    logger.info("Telegram update: %s", body)
    try:
        from services.telegram_bot import handle_telegram_update
        result = await handle_telegram_update(body, db.pool)
        return result
    except Exception as e:
        logger.error("Telegram handler error: %s", e)
        return {"ok": True}
