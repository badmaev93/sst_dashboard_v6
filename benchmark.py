import asyncio
import time
import asyncpg
from services.notification import notify_supervisors
from unittest.mock import AsyncMock

async def main():
    pool = AsyncMock()
    # Mock pool.fetch to return 100 supervisors
    pool.fetch.return_value = [{'telegram_chat_id': i} for i in range(100)]

    # Mock send_telegram to return immediately (we only care about the db queries overhead)
    import services.notification
    services.notification.send_telegram = AsyncMock()

    start = time.time()
    for _ in range(100):
        await notify_supervisors(pool, "Test message")
    end = time.time()

    print(f"Time taken: {end - start:.4f}s")
    print(f"Executes executed: {pool.execute.call_count}")
    print(f"Executemanys executed: {pool.executemany.call_count}")

asyncio.run(main())
