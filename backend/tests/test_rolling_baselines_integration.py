"""Workstream 1 — rolling baseline recomputation, integration-level (real
Postgres, through run_scoring_cycle exactly as the scheduler calls it).

Confirms: a new `baselines` row is inserted per ticker per replay day (not
an update-in-place), sample_size varies realistically as replay advances,
no look-ahead leakage into a given day's own baseline, and the existing
(ticker, trading_day, signal_type) flag upsert still works correctly against
a baseline that changes day-to-day.
"""

from datetime import datetime, timedelta, timezone

from app.providers.historical_replay import HistoricalReplayProvider, ReplayClock, load_history
from app.services.scoring_pipeline import run_scoring_cycle


async def _seed_series(db_pool, ticker, prices):
    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, price in enumerate(prices):
        await db_pool.execute(
            "INSERT INTO price_ticks (ticker, price, volume, ts, source) VALUES ($1, $2, $3, $4, 'real_historical') "
            "ON CONFLICT DO NOTHING",
            ticker, price, 1000, base_ts + timedelta(days=i),
        )


async def test_new_baseline_row_inserted_per_ticker_per_day(db_pool, test_ticker):
    # 50 days of flat +1% history so every replay step has a valid look-ahead-safe baseline.
    prices = [100.0]
    for _ in range(49):
        prices.append(prices[-1] * 1.01)
    await _seed_series(db_pool, test_ticker, prices)

    history = await load_history(db_pool, [test_ticker])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=25))
    sector_map = {test_ticker: "Test"}

    count_before = await db_pool.fetchval("SELECT count(*) FROM baselines WHERE ticker = $1", test_ticker)
    assert count_before == 0

    for _ in range(5):
        result = await run_scoring_cycle(db_pool, provider, [test_ticker], sector_map)
        assert result["scored"] is True
        provider.advance()

    rows = await db_pool.fetch(
        "SELECT as_of_date, sample_size FROM baselines WHERE ticker = $1 ORDER BY as_of_date", test_ticker
    )
    # One distinct row per trading day scored — not a single row overwritten in place.
    assert len(rows) == 5
    as_of_dates = [r["as_of_date"] for r in rows]
    assert as_of_dates == sorted(set(as_of_dates))  # all distinct, chronological

    # sample_size is monotonically non-decreasing as replay advances (more
    # prior history becomes available each day) — the confidence gate is
    # observably alive, not dead code.
    sample_sizes = [r["sample_size"] for r in rows]
    for earlier, later in zip(sample_sizes, sample_sizes[1:]):
        assert later >= earlier


async def test_flag_upsert_still_works_against_a_changing_baseline(db_pool, test_ticker):
    # Mildly noisy history (so baseline stdev isn't near-zero), then a real
    # jump partway through the scored range.
    prices = [100.0]
    for i in range(1, 50):
        prices.append(prices[-1] * (1.0 + (0.003 if i % 2 == 0 else -0.001)))
    prices[40] = prices[39] * 1.05  # a real jump on day 40
    await _seed_series(db_pool, test_ticker, prices)

    history = await load_history(db_pool, [test_ticker])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=35))
    sector_map = {test_ticker: "Test"}

    for _ in range(6):  # steps 35..40, crossing the jump at step 40
        result = await run_scoring_cycle(db_pool, provider, [test_ticker], sector_map)
        assert result["scored"] is True
        provider.advance()

    flags = await db_pool.fetch(
        "SELECT trading_day, z_score, severity FROM flags WHERE ticker = $1 AND signal_type = 'price_zscore'",
        test_ticker,
    )
    assert len(flags) >= 1  # the jump at step 40 produced a real flag against that day's rolling baseline


async def test_no_look_ahead_leakage_baseline_matches_direct_computation(db_pool, test_ticker):
    """Spot-check one day's persisted baseline against a known future price
    move: a huge jump placed AFTER the scored day must not appear in that
    day's stored baseline stats."""
    prices = [100.0 + i * 0.01 for i in range(40)]
    prices[35] = prices[34] * 3.0  # violent future jump, well after the day we'll check
    await _seed_series(db_pool, test_ticker, prices)

    history = await load_history(db_pool, [test_ticker])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=20))
    sector_map = {test_ticker: "Test"}

    result = await run_scoring_cycle(db_pool, provider, [test_ticker], sector_map)
    assert result["scored"] is True

    trading_day = history[test_ticker][20].ts.date()
    row = await db_pool.fetchrow(
        "SELECT mean_return_30d, stdev_return_30d FROM baselines WHERE ticker = $1 AND as_of_date = $2",
        test_ticker, trading_day,
    )
    assert row is not None
    # The future +200% jump (day 35) is nowhere near this day-20 baseline's
    # stats — a leaked value would blow mean/stdev up by orders of magnitude.
    assert abs(float(row["mean_return_30d"])) < 0.05
    assert float(row["stdev_return_30d"]) < 0.05
