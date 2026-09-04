"""Watchlist ownership check — the one authz check that actually matters at
this scale (RELIABILITY.md). Every watchlist-scoped endpoint must resolve
the watchlist through this function, never by trusting a path parameter
alone; a non-existent or non-owned watchlist_id is indistinguishable from
the caller's point of view (404 either way — no resource-existence leak).
"""

import uuid

import asyncpg
from fastapi import HTTPException


async def get_owned_watchlist(pool: asyncpg.Pool, watchlist_id: uuid.UUID, user_id: uuid.UUID) -> asyncpg.Record:
    row = await pool.fetchrow("SELECT id, user_id, name FROM watchlists WHERE id = $1", watchlist_id)
    if row is None or row["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return row
