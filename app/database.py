import asyncpg
from .config import DB_CONFIG

_pool = None

async def init_pool():
    global _pool
     
    try:
        _pool = await asyncpg.create_pool(**DB_CONFIG)
        print("Database pool initialized successfully")
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        raise

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()

async def get_db_connection():
    global _pool
    async with _pool.acquire() as conn:
        yield conn