import asyncpg
from config import DATABASE_URL

pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return pool

async def close_db():
    global pool
    if pool:
        await pool.close()
        pool = None

async def get_db():
    return pool
