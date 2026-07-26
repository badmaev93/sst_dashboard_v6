"""Сервис уведомлений — Telegram + веб-уведомления."""
import logging
import httpx
from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

async def send_telegram(chat_id: int, message: str):
    if not TELEGRAM_BOT_TOKEN:
        logger.debug("Telegram token not set, skipping notification")
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
            return resp.status_code == 200
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False

async def notify_supervisors(pool, message: str):
    supervisors = await pool.fetch(
        "SELECT telegram_chat_id FROM users WHERE role = 'supervisor' AND telegram_chat_id IS NOT NULL")
    for s in supervisors:
        await send_telegram(s['telegram_chat_id'], message)
        await pool.execute(
            "INSERT INTO notifications (user_id, channel, message) "
            "SELECT id, 'telegram', $1 FROM users WHERE telegram_chat_id = $2",
            message, s['telegram_chat_id'])

async def notify_user(pool, user_id: int, message: str):
    user = await pool.fetchrow("SELECT telegram_chat_id FROM users WHERE id = $1", user_id)
    if user and user['telegram_chat_id']:
        await send_telegram(user['telegram_chat_id'], message)
    await pool.execute(
        "INSERT INTO notifications (user_id, channel, message) VALUES ($1, 'web', $2)",
        user_id, message)
