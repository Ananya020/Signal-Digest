"""Clears accumulated demo/scoring state so a fresh frontend dev session or
demo rehearsal starts clean. Run manually, never automatically.

Truncates: flags, flag_ack, watchlist_ack_state.
Resets: provider_state to mode='normal', frozen_at=NULL, last_successful_fetch=NULL.

Does NOT touch: tickers, price_ticks, baselines (real seeded data),
watchlists, watchlist_items (user-created state) — those are not demo noise.

Run from backend/:
    python -m scripts.reset_demo_state
"""

import asyncio

import asyncpg

from app.config import settings


async def main() -> None:
    pool = await asyncpg.create_pool(settings.database_url)
    try:
        counts_before = {
            "flags": await pool.fetchval("SELECT count(*) FROM flags"),
            "flag_ack": await pool.fetchval("SELECT count(*) FROM flag_ack"),
            "watchlist_ack_state": await pool.fetchval("SELECT count(*) FROM watchlist_ack_state"),
        }

        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("TRUNCATE flag_ack, flags, watchlist_ack_state")
                await conn.execute(
                    """
                    INSERT INTO provider_state (id, mode, frozen_at, last_successful_fetch, updated_at)
                    VALUES (1, 'normal', NULL, NULL, now())
                    ON CONFLICT (id) DO UPDATE
                    SET mode = 'normal', frozen_at = NULL, last_successful_fetch = NULL, updated_at = now()
                    """
                )

        print("=== Demo state reset ===")
        print(f"flags: {counts_before['flags']} -> 0")
        print(f"flag_ack: {counts_before['flag_ack']} -> 0")
        print(f"watchlist_ack_state: {counts_before['watchlist_ack_state']} -> 0")
        print("provider_state: mode=normal, frozen_at=NULL, last_successful_fetch=NULL")
        print("\nUntouched (real seeded data / user-created state): tickers, price_ticks, "
              "baselines, watchlists, watchlist_items")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
