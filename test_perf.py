import asyncio
import logging
import time

from db import close_db, init_db
from services.telegram_bot import _cmd_free_text

logging.basicConfig(level=logging.INFO)

async def test_bot_perf():
    pool = await init_db()

    start = time.time()
    try:
        reply = await _cmd_free_text(12345, "What is the forecast?", pool)
    except Exception as e:
        print(f"Error: {e}")
    end = time.time()
    print(f"Execution time: {end - start:.2f} seconds")

    await close_db()

if __name__ == "__main__":
    asyncio.run(test_bot_perf())
