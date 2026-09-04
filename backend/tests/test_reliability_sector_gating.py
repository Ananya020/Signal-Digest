"""RELIABILITY.md #11 — sector aggregation with missing members. Sector mean
must be computed only over tickers with a valid tick THIS cycle; when fewer
than MIN_SECTOR_PEERS_WITH_DATA (2) other sector members have data,
sector_relative must persist as NULL, not be computed off a partial sector.

Uses a real sector from TICKER_SECTORS (Auto) so the sector_by_ticker map
reflects genuine hand-curated groupings, not a fabricated one — but the
cycle only actually scores one ticker, simulating "most of that sector's
tickers have no fresh tick this cycle" at the integration level (through
run_scoring_cycle), not just the pure sector_relative_tag() unit test
already covered in test_scoring.py.
"""

from datetime import datetime, timedelta, timezone

from app.data.baselines import compute_and_store_baseline
from app.data.tickers import TICKER_SECTORS
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


async def test_sector_relative_null_when_fewer_than_two_peers_ticked_this_cycle(db_pool, test_ticker):
    real_sector = TICKER_SECTORS["MARUTI"]  # "Auto" — a real hand-curated sector

    prices = [100.0 + i for i in range(40)]
    prices[35] = prices[34] * 1.10  # real jump -> guarantees a price_zscore flag
    await _seed_series(db_pool, test_ticker, prices)
    await compute_and_store_baseline(db_pool, test_ticker)

    history = await load_history(db_pool, [test_ticker])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=35))

    # sector_by_ticker declares OTHER real Auto-sector members, but this
    # cycle's `tickers` list (passed to run_scoring_cycle below) only ever
    # ticks test_ticker itself — those other members have no data this
    # cycle, exactly RELIABILITY.md #11's scenario.
    sector_by_ticker = {
        test_ticker: real_sector,
        "MARUTI.NS": real_sector,
        "M&M.NS": real_sector,
        "BAJAJ-AUTO.NS": real_sector,
        "EICHERMOT.NS": real_sector,
    }

    result = await run_scoring_cycle(db_pool, provider, [test_ticker], sector_by_ticker)
    assert result["scored"] is True

    price_flags = [f for f in result["flags"] if f["signal_type"] == "price_zscore"]
    assert len(price_flags) == 1

    row = await db_pool.fetchrow(
        "SELECT sector_relative FROM flags WHERE ticker = $1 AND signal_type = 'price_zscore'", test_ticker
    )
    assert row["sector_relative"] is None  # gated — not computed off a partial sector
