"""Persistence for the single-row `provider_state` table — the source of
truth for current fault mode (Phase 4, DATA_MODEL.md), corrected to also
persist `last_successful_fetch` (see `002_add_last_successful_fetch.sql`
and `app/providers/fault_injecting.py`'s module docstring): a process
restart during a genuine `'stale'` fault was resetting the freshness age
clock to "now" and incorrectly reporting LIVE — a real bug, confirmed via a
simulated-restart test, not a narrow documented limitation. Persisting
`last_successful_fetch` alongside `mode`/`frozen_at` fixes it.

Also persists `replay_step` (`004_persist_replay_step.sql`) — a second
instance of the exact same bug class: `HistoricalReplayProvider`'s
`ReplayClock` was process-memory only, so a restart silently reset replay
to the beginning of history. See `app/providers/fault_injecting.py`'s
`sync_from_db`/`persist`.

Concurrent /admin/fault calls: last-write-wins, no locking — a single
UPSERT on the fixed id=1 row, which is exactly what "authoritative,
demo-operated by one person" calls for (Phase 4 locked decision #6).
"""

from datetime import datetime

import asyncpg


async def load_provider_state(pool: asyncpg.Pool) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "SELECT mode, frozen_at, last_successful_fetch, replay_step, updated_at FROM provider_state WHERE id = 1"
    )


async def save_provider_state(
    pool: asyncpg.Pool,
    mode: str,
    frozen_at: datetime | None,
    last_successful_fetch: datetime | None = None,
    replay_step: int | None = None,
) -> None:
    await pool.execute(
        """
        INSERT INTO provider_state (id, mode, frozen_at, last_successful_fetch, replay_step, updated_at)
        VALUES (1, $1, $2, $3, $4, now())
        ON CONFLICT (id) DO UPDATE
        SET mode = EXCLUDED.mode, frozen_at = EXCLUDED.frozen_at,
            last_successful_fetch = EXCLUDED.last_successful_fetch,
            replay_step = EXCLUDED.replay_step, updated_at = EXCLUDED.updated_at
        """,
        mode, frozen_at, last_successful_fetch, replay_step,
    )
