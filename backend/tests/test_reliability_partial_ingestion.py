"""RELIABILITY.md #9 — partial ingestion (scheduler dies mid-batch).
`run_scoring_cycle` scores tickers one at a time in a single loop, and each
ticker's flag upsert is its OWN committed transaction
(`upsert_flag_with_ack_bust`) — not one all-or-nothing transaction spanning
the whole cycle. This test verifies that property holds under a real
mid-batch failure: an exception raised while processing one ticker must
not undo already-committed flags for tickers processed earlier in the same
cycle, and a subsequent retry must complete the remainder without
duplicating what already succeeded.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.data.baselines import compute_and_store_baseline
from app.providers.historical_replay import HistoricalReplayProvider, ReplayClock, load_history
from app.services import scoring_pipeline


async def _seed_series(db_pool, ticker, prices):
    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, price in enumerate(prices):
        await db_pool.execute(
            "INSERT INTO price_ticks (ticker, price, volume, ts, source) VALUES ($1, $2, $3, $4, 'real_historical') "
            "ON CONFLICT DO NOTHING",
            ticker, price, 1000, base_ts + timedelta(days=i),
        )


async def test_failure_on_one_ticker_does_not_roll_back_earlier_committed_tickers(
    db_pool, test_ticker, test_ticker_2, monkeypatch
):
    # Both tickers get a real jump on the same day so each produces a flag.
    prices_a = [100.0 + i for i in range(40)]
    prices_a[35] = prices_a[34] * 1.10
    prices_b = [100.0 + i for i in range(40)]
    prices_b[35] = prices_b[34] * 1.10
    await _seed_series(db_pool, test_ticker, prices_a)
    await _seed_series(db_pool, test_ticker_2, prices_b)
    await compute_and_store_baseline(db_pool, test_ticker)
    await compute_and_store_baseline(db_pool, test_ticker_2)

    history = await load_history(db_pool, [test_ticker, test_ticker_2])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=35))
    sector_map = {test_ticker: "Test", test_ticker_2: "Test"}

    # Simulate the scheduler dying partway through: test_ticker succeeds
    # (processed first, per the tickers list order), test_ticker_2's
    # baseline load raises — as if the process crashed mid-batch.
    real_load_latest_baseline = scoring_pipeline.load_latest_baseline

    async def flaky_load_latest_baseline(pool, ticker):
        if ticker == test_ticker_2:
            raise RuntimeError("simulated scheduler crash mid-batch")
        return await real_load_latest_baseline(pool, ticker)

    monkeypatch.setattr(scoring_pipeline, "load_latest_baseline", flaky_load_latest_baseline)

    with pytest.raises(RuntimeError, match="simulated scheduler crash"):
        await scoring_pipeline.run_scoring_cycle(db_pool, provider, [test_ticker, test_ticker_2], sector_map)

    # test_ticker's flag(s) committed and survive the later exception
    # untouched (a single real jump can legitimately produce both a
    # price_zscore AND a volatility_regime row for the same ticker).
    rows_a_before_retry = await db_pool.fetch(
        "SELECT id, signal_type FROM flags WHERE ticker = $1", test_ticker
    )
    assert len(rows_a_before_retry) > 0
    ids_a_before_retry = {r["id"] for r in rows_a_before_retry}

    # test_ticker_2 never got as far as writing a flag this cycle.
    row_b = await db_pool.fetchrow("SELECT id FROM flags WHERE ticker = $1", test_ticker_2)
    assert row_b is None

    # Retry (scheduler's next tick, same replay position — nothing advanced
    # since the cycle raised before reaching the caller's advance() call):
    # completes the remainder without duplicating test_ticker's existing rows.
    monkeypatch.setattr(scoring_pipeline, "load_latest_baseline", real_load_latest_baseline)
    result = await scoring_pipeline.run_scoring_cycle(db_pool, provider, [test_ticker, test_ticker_2], sector_map)
    assert result["scored"] is True

    rows_a_after_retry = await db_pool.fetch("SELECT id FROM flags WHERE ticker = $1", test_ticker)
    ids_a_after_retry = {r["id"] for r in rows_a_after_retry}
    assert ids_a_after_retry == ids_a_before_retry  # same row ids — refreshed in place, not duplicated

    rows_b_after = await db_pool.fetch("SELECT id, signal_type FROM flags WHERE ticker = $1", test_ticker_2)
    assert len(rows_b_after) > 0  # remainder completed
