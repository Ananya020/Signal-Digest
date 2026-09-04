"""Freshness gating for the scoring pipeline (RELIABILITY.md #1) and its
composition with Phase 2/3's ack-bust upsert under repeated scheduler-style
calls on unchanged (frozen/stale) data. Exercises run_scoring_cycle
directly — this IS "the scheduler's per-tick logic" (main.py's job calls
this exact function), so testing it this way is deterministic and doesn't
race a real APScheduler interval."""

from datetime import datetime, timedelta, timezone

from app.data.baselines import compute_and_store_baseline
from app.providers.fault_injecting import FaultInjectingProvider
from app.providers.historical_replay import HistoricalReplayProvider, ReplayClock, load_history
from app.services.scoring_pipeline import run_scoring_cycle

THRESHOLDS = dict(live_seconds=5, recent_seconds=15, delayed_seconds=30, stale_seconds=30)


async def _seed_series(db_pool, ticker, prices):
    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, price in enumerate(prices):
        await db_pool.execute(
            "INSERT INTO price_ticks (ticker, price, volume, ts, source) VALUES ($1, $2, $3, $4, 'real_historical') "
            "ON CONFLICT DO NOTHING",
            ticker, price, 1000, base_ts + timedelta(days=i),
        )


async def test_unavailable_creates_no_flags(db_pool, test_ticker):
    prices = [100.0 + i for i in range(40)]
    await _seed_series(db_pool, test_ticker, prices)
    await compute_and_store_baseline(db_pool, test_ticker)

    history = await load_history(db_pool, [test_ticker])
    wrapped = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=35))
    provider = FaultInjectingProvider(wrapped=wrapped, **THRESHOLDS)
    provider.set_mode("outage")

    count_before = await db_pool.fetchval("SELECT count(*) FROM flags WHERE ticker = $1", test_ticker)
    result = await run_scoring_cycle(db_pool, provider, [test_ticker], {test_ticker: "Test"})

    assert result["scored"] is False
    assert result["reason"] == "UNAVAILABLE"
    assert result["flags"] == []

    count_after = await db_pool.fetchval("SELECT count(*) FROM flags WHERE ticker = $1", test_ticker)
    assert count_after == count_before == 0


async def test_repeated_stale_ticks_do_not_spuriously_bust_ack_or_duplicate(db_pool, test_ticker, test_watchlist):
    prices = [100.0 + i for i in range(40)]
    prices[35] = prices[34] * 1.10  # a real jump, to guarantee a flag fires at step 35
    await _seed_series(db_pool, test_ticker, prices)
    await compute_and_store_baseline(db_pool, test_ticker)

    history = await load_history(db_pool, [test_ticker])
    wrapped = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=35))
    provider = FaultInjectingProvider(wrapped=wrapped, **THRESHOLDS)
    provider.set_mode("stale")

    sector_map = {test_ticker: "Test"}
    result1 = await run_scoring_cycle(db_pool, provider, [test_ticker], sector_map)
    assert result1["scored"] is True
    assert len(result1["flags"]) >= 1
    flag_id = result1["flags"][0]["id"]
    total_flags_after_first_run = len(result1["flags"])

    await db_pool.execute(
        "INSERT INTO flag_ack (flag_id, watchlist_id, acked_at) VALUES ($1, $2, now())",
        flag_id, test_watchlist,
    )

    for _ in range(3):
        provider.advance()  # no-op — frozen while stale
        result = await run_scoring_cycle(db_pool, provider, [test_ticker], sector_map)
        assert result["scored"] is True
        assert len(result["flags"]) == total_flags_after_first_run
        for flag in result["flags"]:
            assert flag["was_insert"] is False  # same row updated, not re-inserted
            assert flag["ack_busted"] is False  # unchanged severity on unchanged frozen data

    still_acked = await db_pool.fetchval(
        "SELECT 1 FROM flag_ack WHERE flag_id = $1 AND watchlist_id = $2", flag_id, test_watchlist
    )
    assert still_acked == 1

    total_rows = await db_pool.fetchval("SELECT count(*) FROM flags WHERE ticker = $1", test_ticker)
    assert total_rows == total_flags_after_first_run  # no duplicate rows across repeats
