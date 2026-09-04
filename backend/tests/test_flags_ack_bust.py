"""Ack-bust transaction correctness — the highest-stakes logic in the
project (CLAUDE.md). Run against a real Postgres instance, not mocks: this
is a transaction-boundary question, and mocking the DB would hide exactly
the class of bug this logic exists to prevent.
"""

from dataclasses import replace
from datetime import date, datetime, timezone

from app.services.flags import upsert_flag_with_ack_bust
from app.services.scoring import FlagCandidate


def make_candidate(ticker: str, **overrides) -> FlagCandidate:
    defaults = dict(
        ticker=ticker,
        trading_day=date(2026, 1, 1),
        signal_type="price_zscore",
        z_score=2.1,
        severity="notable",
        severity_rank=1,
        volume_ratio=1.5,
        sector_relative=None,
        computed_at=datetime.now(timezone.utc),
        provider_state_at_computation="replay_simulated",
    )
    defaults.update(overrides)
    return FlagCandidate(**defaults)


async def ack_flag(db_pool, flag_id: int, watchlist_id) -> None:
    await db_pool.execute(
        "INSERT INTO flag_ack (flag_id, watchlist_id, acked_at) VALUES ($1, $2, now())",
        flag_id, watchlist_id,
    )


async def is_acked(db_pool, flag_id: int, watchlist_id) -> bool:
    row = await db_pool.fetchrow(
        "SELECT 1 FROM flag_ack WHERE flag_id = $1 AND watchlist_id = $2", flag_id, watchlist_id
    )
    return row is not None


async def test_escalation_busts_ack(db_pool, test_ticker, test_watchlist):
    notable = make_candidate(test_ticker, severity="notable", severity_rank=1, z_score=2.1)
    async with db_pool.acquire() as conn:
        result1 = await upsert_flag_with_ack_bust(conn, notable)
    assert result1.was_insert is True

    await ack_flag(db_pool, result1.id, test_watchlist)
    assert await is_acked(db_pool, result1.id, test_watchlist) is True

    extreme = replace(notable, severity="extreme", severity_rank=3, z_score=3.6)
    async with db_pool.acquire() as conn:
        result2 = await upsert_flag_with_ack_bust(conn, extreme)

    assert result2.was_insert is False
    assert result2.severity_rank == 3
    assert result2.ack_busted is True
    assert await is_acked(db_pool, result1.id, test_watchlist) is False  # ack gone

    row = await db_pool.fetchrow("SELECT severity, severity_rank, z_score FROM flags WHERE id = $1", result1.id)
    assert row["severity"] == "extreme"
    assert row["severity_rank"] == 3
    assert float(row["z_score"]) == 3.6


async def test_deescalation_does_not_bust_ack(db_pool, test_ticker, test_watchlist):
    extreme = make_candidate(test_ticker, severity="extreme", severity_rank=3, z_score=3.6)
    async with db_pool.acquire() as conn:
        result1 = await upsert_flag_with_ack_bust(conn, extreme)
    assert result1.was_insert is True

    await ack_flag(db_pool, result1.id, test_watchlist)

    notable = replace(extreme, severity="notable", severity_rank=1, z_score=2.1)
    async with db_pool.acquire() as conn:
        result2 = await upsert_flag_with_ack_bust(conn, notable)

    assert result2.was_insert is False
    assert result2.severity_rank == 1
    assert result2.ack_busted is False
    # Negative-space assertion: de-escalation must NOT clear the ack.
    assert await is_acked(db_pool, result1.id, test_watchlist) is True

    row = await db_pool.fetchrow("SELECT severity, severity_rank FROM flags WHERE id = $1", result1.id)
    assert row["severity"] == "notable"
    assert row["severity_rank"] == 1


async def test_equal_severity_rerun_leaves_ack_but_refreshes_evidence(db_pool, test_ticker, test_watchlist):
    """Regression test for the corrected design (see flags.py module
    docstring): equal severity_rank must NOT bust the ack, but the flag's
    evidence fields (z_score, volume_ratio, sector_relative, computed_at,
    provider_state_at_computation) must still be refreshed to the latest
    computation — they must never go stale just because the severity band
    didn't change."""
    notable = make_candidate(
        test_ticker, severity="notable", severity_rank=1, z_score=2.1,
        volume_ratio=1.5, sector_relative=None, provider_state_at_computation="replay_simulated",
    )
    async with db_pool.acquire() as conn:
        result1 = await upsert_flag_with_ack_bust(conn, notable)
    await ack_flag(db_pool, result1.id, test_watchlist)

    later = datetime.now(timezone.utc)
    same_rank_new_evidence = replace(
        notable, z_score=2.4, volume_ratio=1.9, sector_relative="sector_wide",
        computed_at=later, provider_state_at_computation="fault_injected",
    )
    async with db_pool.acquire() as conn:
        result2 = await upsert_flag_with_ack_bust(conn, same_rank_new_evidence)

    assert result2.was_insert is False
    assert result2.ack_busted is False
    assert result2.severity_rank == 1
    # Ack must survive — same severity band, nothing new to alert on.
    assert await is_acked(db_pool, result1.id, test_watchlist) is True

    row = await db_pool.fetchrow(
        "SELECT z_score, volume_ratio, sector_relative, computed_at, "
        "provider_state_at_computation, severity_rank FROM flags WHERE id = $1",
        result1.id,
    )
    assert float(row["z_score"]) == 2.4  # refreshed, not stale
    assert float(row["volume_ratio"]) == 1.9
    assert row["sector_relative"] == "sector_wide"
    assert row["provider_state_at_computation"] == "fault_injected"
    assert row["computed_at"] == later
    assert row["severity_rank"] == 1


async def test_postgres_returning_yields_zero_rows_when_conflict_where_is_false(db_pool):
    """Directly verifies Postgres's own RETURNING behavior (not our code) so
    the fix in flags.py rests on observed fact, not inference from final DB
    state: when ON CONFLICT DO UPDATE ... WHERE evaluates false, RETURNING
    yields zero rows — not the old row, not a partial update. This is why
    the corrected upsert in flags.py uses an unconditional SET (no WHERE):
    a conditional WHERE on this clause would silently drop evidence updates
    whenever it evaluated false, exactly as it did before the fix."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DROP TABLE IF EXISTS _returning_probe")
            await conn.execute("CREATE TABLE _returning_probe (k INT PRIMARY KEY, v INT)")
            await conn.execute("INSERT INTO _returning_probe (k, v) VALUES (1, 100)")

            row = await conn.fetchrow(
                """
                INSERT INTO _returning_probe (k, v) VALUES (1, 100)
                ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v
                WHERE EXCLUDED.v IS DISTINCT FROM _returning_probe.v
                RETURNING k, v
                """
            )
            assert row is None  # zero rows returned, confirmed directly

            await conn.execute("DROP TABLE _returning_probe")


async def test_first_insert_never_busts_ack_because_nothing_was_acked_yet(db_pool, test_ticker):
    notable = make_candidate(test_ticker)
    async with db_pool.acquire() as conn:
        result = await upsert_flag_with_ack_bust(conn, notable)
    assert result.was_insert is True
    assert result.ack_busted is False
