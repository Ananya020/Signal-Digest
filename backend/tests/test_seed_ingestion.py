from datetime import datetime, timezone

import pandas as pd

from app.data.tickers import TICKER_SECTORS, to_nse_symbol
from scripts.seed_historical_data import classify_failure, insert_price_ticks


def test_all_universe_tickers_map_to_ns_suffixed_symbols():
    for bare_symbol in TICKER_SECTORS:
        nse_symbol = to_nse_symbol(bare_symbol)
        assert nse_symbol == f"{bare_symbol}.NS"
        assert nse_symbol.endswith(".NS")


def test_classify_failure_distinguishes_rate_limit_from_other_exceptions():
    assert "rate-limited" in classify_failure(Exception("HTTP Error 429: Too Many Requests"), None)
    assert "exception" in classify_failure(ValueError("boom"), None)


def test_classify_failure_empty_response():
    assert classify_failure(None, pd.DataFrame()) == "empty response (no data returned by yfinance)"


async def test_ingestion_stores_ns_suffixed_ticker_with_real_historical_source(db_pool, test_ticker):
    df = pd.DataFrame(
        {"Close": [100.0, 101.0], "Volume": [1000, 1100]},
        index=pd.DatetimeIndex(
            [datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc)]
        ),
    )

    await insert_price_ticks(db_pool, test_ticker, df)

    rows = await db_pool.fetch(
        "SELECT ticker, source FROM price_ticks WHERE ticker = $1", test_ticker
    )
    assert len(rows) == 2
    assert all(r["ticker"] == test_ticker for r in rows)
    assert all(r["source"] == "real_historical" for r in rows)


async def test_rerunning_ingestion_does_not_create_duplicates(db_pool, test_ticker):
    df = pd.DataFrame(
        {"Close": [100.0, 101.0], "Volume": [1000, 1100]},
        index=pd.DatetimeIndex(
            [datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc)]
        ),
    )

    await insert_price_ticks(db_pool, test_ticker, df)
    await insert_price_ticks(db_pool, test_ticker, df)  # re-run, same data

    count = await db_pool.fetchval(
        "SELECT count(*) FROM price_ticks WHERE ticker = $1", test_ticker
    )
    assert count == 2  # not 4 — UNIQUE(ticker, ts, source) + ON CONFLICT DO NOTHING held


async def test_a_failed_ticker_does_not_block_others(db_pool, test_ticker):
    """Simulates the batch loop's per-ticker isolation: one ticker's data
    never reaches insert_price_ticks (as if its yfinance call failed), while
    another proceeds independently and succeeds."""
    good_df = pd.DataFrame(
        {"Close": [100.0], "Volume": [1000]},
        index=pd.DatetimeIndex([datetime(2026, 1, 1, tzinfo=timezone.utc)]),
    )

    # "failed" ticker: nothing inserted for it, no exception raised to the caller
    rows_seen, stored = await insert_price_ticks(db_pool, "DOES-NOT-EXIST.NS", pd.DataFrame())
    assert (rows_seen, stored) == (0, 0)

    # good ticker still succeeds independently
    rows_seen, stored = await insert_price_ticks(db_pool, test_ticker, good_df)
    assert rows_seen == 1 and stored == 1
