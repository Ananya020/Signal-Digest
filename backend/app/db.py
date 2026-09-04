import asyncpg

from app.config import settings

pool: asyncpg.Pool | None = None


async def connect_db() -> None:
    global pool
    pool = await asyncpg.create_pool(settings.database_url)


async def disconnect_db() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    return pool
