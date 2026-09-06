"""Clears accumulated demo/scoring state so a fresh frontend dev session or
demo rehearsal starts clean. Run manually, never automatically.

Truncates: flags, flag_ack, flag_ack_history, watchlist_ack_state.

Bug fixed (2026-09-06): `flag_ack_history` (added in the Signal Evolution /
"since you last checked" workstream, migrations/003_since_last_checked.sql)
references `flags(id)`. Postgres's TRUNCATE requires every table with a
foreign key into a truncated table to be included in the SAME TRUNCATE
statement (or CASCADE) — this script's TRUNCATE was never updated when that
table was added, so it failed against the real Render DB with
FeatureNotSupportedError the first time flag_ack_history actually had rows.
Fixed by adding it explicitly to the TRUNCATE list, not via CASCADE — an
explicit list is what lets `tests/test_reset_demo_state_truncate_scope.py`
catch this class of bug the next time a new table gains an FK into one of
these; CASCADE would silently paper over a future instance of the exact same
mistake instead of failing loudly.

Resets: provider_state to mode='normal', frozen_at=NULL, last_successful_fetch=NULL.
Deliberately does NOT reset provider_state.replay_step — a demo/dev reset
clearing accumulated flags has no bearing on where real historical replay
should resume from; resetting it would silently discard real restart-
resilience state for an unrelated reason (see PROGRESS.md's replay_step
persistence fix).

Does NOT touch: tickers, price_ticks, baselines (real seeded data),
watchlists, watchlist_items (user-created state) — those are not demo noise.

Run from backend/:
    python -m scripts.reset_demo_state
"""

import asyncio

import asyncpg

from app.config import settings

# Single source of truth for what this script truncates — imported directly
# by tests/test_reset_demo_state_truncate_scope.py, which checks via schema
# introspection that every table with a foreign key into any of these is
# itself listed here. Keep this in sync with the TRUNCATE statement below
# (it IS the TRUNCATE statement's table list — see main()).
TRUNCATE_TABLES = ["flag_ack", "flag_ack_history", "flags", "watchlist_ack_state"]


async def main() -> None:
    pool = await asyncpg.create_pool(settings.database_url)
    try:
        counts_before = {
            "flags": await pool.fetchval("SELECT count(*) FROM flags"),
            "flag_ack": await pool.fetchval("SELECT count(*) FROM flag_ack"),
            "flag_ack_history": await pool.fetchval("SELECT count(*) FROM flag_ack_history"),
            "watchlist_ack_state": await pool.fetchval("SELECT count(*) FROM watchlist_ack_state"),
        }

        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(f"TRUNCATE {', '.join(TRUNCATE_TABLES)}")
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
        print(f"flag_ack_history: {counts_before['flag_ack_history']} -> 0")
        print(f"watchlist_ack_state: {counts_before['watchlist_ack_state']} -> 0")
        print("provider_state: mode=normal, frozen_at=NULL, last_successful_fetch=NULL")
        print("\nUntouched (real seeded data / user-created state): tickers, price_ticks, "
              "baselines, watchlists, watchlist_items")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
