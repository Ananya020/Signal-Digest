"""Regression test for a real bug found while building the E2E demo
rehearsal test: both `seed_demo_escalation_precondition.py` and the new
`find_escalation_candidate.py` independently pre-verify a trading day's
"real" severity using `compute_baseline_as_of` + `z_score` + `severity_band`
directly — but neither originally checked `sample_size >= MIN_SAMPLE_SIZE`,
the same confidence gate `score_price_zscore()` (the real pipeline) enforces.
Without that check, a script could "verify" a severity for a day the real
pipeline would actually suppress (insufficient history) — a seeded
escalation-flip placeholder for such a day would never get corrected, and a
live demo would hang waiting for a flip that can never happen.
"""

from datetime import datetime, timedelta, timezone

import pytest

from scripts.find_escalation_candidate import find_candidate
from scripts.seed_demo_escalation_precondition import verify_and_seed


async def _seed_series(db_pool, ticker, prices):
    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, price in enumerate(prices):
        await db_pool.execute(
            "INSERT INTO price_ticks (ticker, price, volume, ts, source) VALUES ($1, $2, $3, $4, 'real_historical') "
            "ON CONFLICT DO NOTHING",
            ticker, price, 1000, base_ts + timedelta(days=i),
        )


async def test_seed_script_refuses_a_day_with_insufficient_sample_size(db_pool, test_ticker, test_watchlist):
    # Only 10 days of history before the target day -> sample_size=9,
    # well below MIN_SAMPLE_SIZE=20, even though the move itself is huge
    # enough to cross the severity trigger if the gate were skipped.
    prices = [100.0] * 10 + [200.0]  # day 10 (index 10): a real +100% move
    await _seed_series(db_pool, test_ticker, prices)
    trading_day = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=10)).date()

    with pytest.raises(SystemExit, match="sample_size"):
        await verify_and_seed(db_pool, test_ticker, trading_day, str(test_watchlist), placeholder_rank=1)

    # Confirm nothing was written — a refused verification must not seed a
    # flag/ack that a live scheduler would then wait forever to correct.
    row = await db_pool.fetchrow("SELECT id FROM flags WHERE ticker = $1", test_ticker)
    assert row is None


async def test_find_candidate_never_returns_a_day_below_min_sample_size(db_pool, test_ticker):
    # Same fixture: a huge move at index 10, but only 10 prior days of
    # history — find_candidate must skip it (severity_band would otherwise
    # match on the raw z-score alone).
    prices = [100.0] * 10 + [200.0]
    await _seed_series(db_pool, test_ticker, prices)

    result = await find_candidate(min_step=0, min_severity_rank=1, tickers=[test_ticker])
    assert result is None  # the only real move in this series is gated out
