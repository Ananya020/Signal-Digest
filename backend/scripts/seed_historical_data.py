"""One-off manual backfill: pulls ~1 year of daily OHLCV for the fixed ticker
universe (app.data.tickers.TICKER_SECTORS) via yfinance, stores it in
`tickers` / `price_ticks` (source='real_historical'), then computes and
stores a baseline row per successfully-seeded ticker.

Not a service — run manually:
    python -m scripts.seed_historical_data
(from backend/, with the venv active; reads DB config from the same
pydantic-settings `.env` the app uses — see app/config.py)

Safe to re-run: tickers upsert on PK, price_ticks upsert relies on the
DB-enforced UNIQUE(ticker, ts, source) constraint (ON CONFLICT DO NOTHING),
baselines upsert on (ticker, as_of_date).
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone

import asyncpg
import pandas as pd
import yfinance as yf

from app.config import settings
from app.data.baselines import compute_and_store_baseline
from app.data.tickers import TICKER_SECTORS, to_nse_symbol

IST = timezone(timedelta(hours=5, minutes=30))
REQUEST_DELAY_SECONDS = 0.5
HISTORY_PERIOD = "1y"


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance can return MultiIndex columns (e.g. when a batch download
    path is used internally); normalize to plain column names defensively
    even though we call per-ticker."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def _trading_day_close_ts(day: pd.Timestamp) -> datetime:
    """Historical daily bars represent the NSE close for that trading day.
    Anchor to 15:30 IST (NSE close) and store as UTC, consistent with
    RELIABILITY.md's 'all timestamps UTC internally, trading-day boundaries
    computed in Asia/Kolkata' rule."""
    d = day.to_pydatetime()
    local_close = datetime(d.year, d.month, d.day, 15, 30, tzinfo=IST)
    return local_close.astimezone(timezone.utc)


def classify_failure(exc: Exception | None, df: pd.DataFrame | None) -> str:
    if exc is not None:
        msg = str(exc)
        if "429" in msg or "rate limit" in msg.lower() or "too many requests" in msg.lower():
            return f"rate-limited: {msg}"
        return f"exception: {msg}"
    if df is None or df.empty:
        return "empty response (no data returned by yfinance)"
    return "unknown"


async def upsert_ticker(pool: asyncpg.Pool, nse_symbol: str, bare_symbol: str, sector: str) -> None:
    await pool.execute(
        """
        INSERT INTO tickers (ticker, name, sector)
        VALUES ($1, $2, $3)
        ON CONFLICT (ticker) DO UPDATE SET name = EXCLUDED.name, sector = EXCLUDED.sector
        """,
        nse_symbol,
        bare_symbol,  # no external metadata API for a display name, per PRODUCT.md constraint
        sector,
    )


async def insert_price_ticks(pool: asyncpg.Pool, nse_symbol: str, df: pd.DataFrame) -> tuple[int, int]:
    rows = []
    for idx, row in df.iterrows():
        close = row.get("Close")
        volume = row.get("Volume")
        if pd.isna(close) or pd.isna(volume):
            continue  # do not fabricate a value for a missing observation
        rows.append(
            (
                nse_symbol,
                float(close),
                int(volume),
                _trading_day_close_ts(idx),
                "real_historical",
            )
        )

    if not rows:
        return 0, 0

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.executemany(
                """
                INSERT INTO price_ticks (ticker, price, volume, ts, source)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (ticker, ts, source) DO NOTHING
                """,
                rows,
            )
    # asyncpg's executemany doesn't report per-row conflict counts directly;
    # re-query actual stored count for this ticker/source to get real numbers.
    stored = await pool.fetchval(
        "SELECT count(*) FROM price_ticks WHERE ticker = $1 AND source = 'real_historical'",
        nse_symbol,
    )
    return len(rows), stored or 0


async def main() -> int:
    pool = await asyncpg.create_pool(settings.database_url)

    attempted = 0
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []
    total_rows_seen = 0
    total_rows_in_table_after: dict[str, int] = {}

    try:
        for bare_symbol, sector in TICKER_SECTORS.items():
            nse_symbol = to_nse_symbol(bare_symbol)
            attempted += 1
            print(f"[seed] fetching {nse_symbol} ...", flush=True)

            df = None
            exc: Exception | None = None
            try:
                df = yf.Ticker(nse_symbol).history(period=HISTORY_PERIOD, auto_adjust=True)
                df = _flatten_columns(df)
            except Exception as e:  # noqa: BLE001 — must not crash the batch
                exc = e

            if exc is not None or df is None or df.empty:
                reason = classify_failure(exc, df)
                print(f"[seed] FAILED {nse_symbol}: {reason}", flush=True)
                failed.append((nse_symbol, reason))
                time.sleep(REQUEST_DELAY_SECONDS)
                continue

            await upsert_ticker(pool, nse_symbol, bare_symbol, sector)
            rows_seen, rows_now_in_table = await insert_price_ticks(pool, nse_symbol, df)
            total_rows_seen += rows_seen
            total_rows_in_table_after[nse_symbol] = rows_now_in_table
            succeeded.append(nse_symbol)
            print(
                f"[seed] OK {nse_symbol}: {rows_seen} observations fetched, "
                f"{rows_now_in_table} total real_historical rows now stored",
                flush=True,
            )

            time.sleep(REQUEST_DELAY_SECONDS)

        print("\n[seed] computing baselines for successfully seeded tickers ...", flush=True)
        baseline_count = 0
        for nse_symbol in succeeded:
            result = await compute_and_store_baseline(pool, nse_symbol)
            if result is not None:
                baseline_count += 1

        total_stored_now = sum(total_rows_in_table_after.values())
        skipped_duplicates = max(0, total_rows_seen - total_stored_now) if succeeded else 0

        print("\n=== Seed summary ===")
        print(f"Tickers attempted: {attempted}")
        print(f"Successful: {len(succeeded)}")
        print(f"Failed: {len(failed)}" + (f" ({', '.join(f'{t}: {r}' for t, r in failed)})" if failed else ""))
        print(f"Price ticks inserted (this run, pre-dedup): {total_rows_seen}")
        print(f"Price ticks now stored (real_historical, post ON CONFLICT dedup): {total_stored_now}")
        print(f"Baselines computed: {baseline_count}")

        return 0 if succeeded else 1
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
