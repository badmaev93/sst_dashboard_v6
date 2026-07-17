"""
AI LLM client — Gemini Flash Lite (primary) with GigaChat (Sber) fallback.
Displayed as "GigaChat" in the UI for branding consistency.
"""
import base64
import logging
import time
from typing import Optional

import httpx

from config import (
    ANTHROPIC_API_KEY,
    GIGACHAT_CLIENT_ID, GIGACHAT_CLIENT_SECRET, GIGACHAT_SCOPE,
    GEMINI_API_KEY,
)

logger = logging.getLogger(__name__)

# ── Google Gemini Flash Lite (primary) ───────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


async def _gemini_chat(system_prompt: str, user_message: str,
                       max_tokens: int = 800, temperature: float = 0.7) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    try:
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_message}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GEMINI_API_URL,
                params={"key": GEMINI_API_KEY},
                json=payload,
                headers={"content-type": "application/json"},
            )
        if resp.status_code != 200:
            logger.warning("Gemini API error %d: %s", resp.status_code, resp.text[:300])
            return None
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.warning("Gemini API exception: %s", e)
        return None


# ── GigaChat (Sber) fallback ────────────────────────────────────────────────
AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_API_BASE = "https://gigachat.devices.sberbank.ru/api/v1"
GIGACHAT_MODEL = "GigaChat"

_gc_token: Optional[str] = None
_gc_token_expires: float = 0.0


async def _gc_get_token() -> Optional[str]:
    global _gc_token, _gc_token_expires
    if _gc_token and time.time() < _gc_token_expires - 60:
        return _gc_token
    if not GIGACHAT_CLIENT_ID or not GIGACHAT_CLIENT_SECRET:
        return None
    try:
        creds = base64.b64encode(
            f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}".encode()).decode()
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.post(
                AUTH_URL,
                headers={
                    "Authorization": f"Basic {creds}",
                    "RqUID": "sst-bot-001",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"scope": GIGACHAT_SCOPE},
            )
        if resp.status_code != 200:
            logger.error("GigaChat auth failed %d: %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        _gc_token = data["access_token"]
        _gc_token_expires = data.get("expires_at", time.time() + 1800) / 1000
        return _gc_token
    except Exception as e:
        logger.error("GigaChat auth error: %s", e)
        return None


async def _gigachat_chat(system_prompt: str, user_message: str,
                         max_tokens: int = 800, temperature: float = 0.7) -> Optional[str]:
    token = await _gc_get_token()
    if not token:
        return None
    try:
        payload = {
            "model": GIGACHAT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.post(
                f"{GIGACHAT_API_BASE}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code != 200:
            logger.error("GigaChat error %d: %s", resp.status_code, resp.text[:300])
            return None
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error("GigaChat exception: %s", e)
        return None


# ── Public API (tries Gemini first, then GigaChat) ───────────────────────────

async def chat(system_prompt: str, user_message: str,
               max_tokens: int = 800, temperature: float = 0.7) -> Optional[str]:
    result = await _gemini_chat(system_prompt, user_message, max_tokens, temperature)
    if result:
        return result
    return await _gigachat_chat(system_prompt, user_message, max_tokens, temperature)


async def analyze_station_data(station_name: str, readings: list[dict]) -> str:
    if not readings:
        return "Нет данных для анализа."
    latest = readings[0]
    system = (
        "Ты — аналитик морских данных. Отвечай кратко (2-3 предложения), "
        "на русском языке, в стиле профессионального метеорологического бюллетеня."
    )
    user = (
        f"Станция {station_name}. Последние данные:\n"
        f"ТПО: {latest.get('sst')}°C, Ветер: {latest.get('wind_speed')} м/с, "
        f"Высота волн: {latest.get('wave_height')} м, Статус: {latest.get('status', 'normal')}.\n"
        f"Дай краткую оценку гидрометеорологической обстановки."
    )
    result = await chat(system, user, max_tokens=200)
    return result or f"Станция {station_name}: ТПО {latest.get('sst')}°C, ветер {latest.get('wind_speed')} м/с."


async def summarize_daily_report(station_summaries: list[dict],
                                  anomaly_count: int,
                                  pending_requests: int) -> str:
    system = (
        "Ты — автоматизированная система мониторинга морских станций. "
        "Пиши кратко, по делу, как официальный гидрометеорологический бюллетень. "
        "Используй эмодзи для читаемости."
    )
    summaries_text = "\n".join(
        f"• {s['name']} ({s['code']}): ТПО {s.get('sst', '—')}°C, "
        f"ветер {s.get('wind_speed', '—')} м/с, статус {s.get('status', '—')}"
        for s in station_summaries[:10]
    )
    user = (
        f"Ежедневная сводка по сети станций Дальнего Востока:\n"
        f"{summaries_text}\n\n"
        f"Аномалий за сутки: {anomaly_count}\n"
        f"Заявок на подписи: {pending_requests}\n\n"
        f"Напиши краткий бюллетень (4-6 строк)."
    )
    return await chat(system, user, max_tokens=400) or "Ежедневная сводка сформирована."
