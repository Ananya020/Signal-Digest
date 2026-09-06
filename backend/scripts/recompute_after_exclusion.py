"""One-off maintenance script: recomputes baselines and re-scores flags for
the trading-day window whose 30-day trailing return series was contaminated
by a known data exclusion (app/data/exclusions.py) — specifically TRENT.NS
and ITC.NS's 2026-01-01 corporate-action artifact, and the ~30 trading days
after it for each affected ticker (the exact span whose baseline window used
to include that excluded return; recomputing beyond that span is a no-op
since the excluded return has already aged out of a 30-day window there).

Not a permanent part of the pipeline — this is a corrective backfill run
once, locally, after app/data/exclusions.py gained new entries. The live
scheduler/replay path (scoring_pipeline.run_scoring_cycle) already applies
the exclusion automatically on every future cycle via baselines.py; this
script only needs to touch the window that was ALREADY computed and stored
before the exclusion existed.

Uses the exact same building blocks scoring_pipeline.run_scoring_cycle uses
(compute_baseline_as_of, score_price_zscore, score_volatility_regime,
upsert_flag_with_ack_bust) — none of them modified — just driven by explicit
historical dates instead of "whatever the live replay tick currently is".

Run from backend/:
    python -m scripts.recompute_after_exclusion [--dry-run]
"""

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import asyncpg

from app.config import settings
from app.data.baselines import compute_baseline_as_of, load_baseline_as_of, load_price_series, upsert_baseline
from app.data.exclusions import KNOWN_EXCLUSIONS
from app.data.tickers import TICKER_SECTORS, to_nse_symbol
from app.services.flags import upsert_flag_with_ack_bust
from app.services.scoring import compute_return, score_price_zscore, score_volatility_regime

IST = ZoneInfo("Asia/Kolkata")
WINDOW_TRADING_DAYS = 30  # matches baselines.py's rolling window length

SECTOR_BY_NSE_TICKER = {to_nse_symbol(bare): sector for bare, sector in TICKER_SECTORS.items()}


async def build_return_by_date(pool: asyncpg.Pool, ticker: str) -> dict:
    """ticker's own {trading_day: (return, volume)} map, same attribution
    convention as baselines.py/trading_day_from_tick (return_t uses close_t
    vs close_(t-1); trading_day derived via IST, not raw UTC date)."""
    series = await load_price_series(pool, ticker)
    by_date: dict = {}
    for i in range(1, len(series)):
        trading_day = series[i].ts.astimezone(IST).date()
        by_date[trading_day] = (compute_return(series[i - 1].price, series[i].price), series[i].volume)
    return by_date


async def run(pool: asyncpg.Pool, dry_run: bool) -> None:
    # Peer return series, loaded once per sector actually needed.
    peer_returns_cache: dict[str, dict] = {}

    for exclusion in KNOWN_EXCLUSIONS:
        ticker = exclusion.ticker
        sector = SECTOR_BY_NSE_TICKER.get(ticker)
        print(f"\n=== {ticker}: recomputing window after excluded {exclusion.excluded_date} ===")

        series = await load_price_series(pool, ticker)
        all_trading_days = sorted({p.ts.astimezone(IST).date() for p in series})
        affected_days = [d for d in all_trading_days if d > exclusion.excluded_date][:WINDOW_TRADING_DAYS]

        if not affected_days:
            print(f"  no trading days after {exclusion.excluded_date} found — nothing to recompute")
            continue

        own_returns = await build_return_by_date(pool, ticker)

        sector_peers = [
            to_nse_symbol(bare) for bare, sec in TICKER_SECTORS.items() if sec == sector and to_nse_symbol(bare) != ticker
        ]
        for peer in sector_peers:
            if peer not in peer_returns_cache:
                peer_returns_cache[peer] = await build_return_by_date(pool, peer)

        for trading_day in affected_days:
            before = await load_baseline_as_of(pool, ticker, trading_day)
            before_stdev = before.stdev_return_30d if before else None
            before_sample = before.sample_size if before else None

            baseline = compute_baseline_as_of(ticker, series, trading_day)
            if baseline is None:
                print(f"  {trading_day}: no baseline computable (no prior history) — skipping")
                continue

            if dry_run:
                print(
                    f"  {trading_day}: sample_size {before_sample} -> {baseline.sample_size}, "
                    f"stdev_return_30d {before_stdev} -> {baseline.stdev_return_30d} (DRY RUN, not persisted)"
                )
                continue

            await upsert_baseline(pool, baseline)

            if trading_day not in own_returns:
                print(f"  {trading_day}: baseline recomputed (no own tick this day to re-score)")
                continue
            today_return, today_volume = own_returns[trading_day]

            peer_returns = [
                peer_returns_cache[peer][trading_day][0]
                for peer in sector_peers
                if trading_day in peer_returns_cache[peer]
            ]

            candidates = []
            price_flag = score_price_zscore(
                ticker=ticker,
                trading_day=trading_day,
                today_return=today_return,
                today_volume=today_volume,
                baseline=baseline,
                peer_returns=peer_returns,
                computed_at=datetime.now(timezone.utc),
                provider_state="real_historical",
            )
            if price_flag:
                candidates.append(price_flag)
            vol_flag = score_volatility_regime(
                ticker=ticker,
                trading_day=trading_day,
                baseline=baseline,
                computed_at=datetime.now(timezone.utc),
                provider_state="real_historical",
            )
            if vol_flag:
                candidates.append(vol_flag)

            results = []
            async with pool.acquire() as conn:
                for candidate in candidates:
                    result = await upsert_flag_with_ack_bust(conn, candidate)
                    results.append((candidate, result))

            summary = ", ".join(
                f"{c.signal_type}={c.severity}(z={c.z_score})" + (" [ack_busted]" if r.ack_busted else "")
                for c, r in results
            ) or "no flag (below trigger or gated)"
            print(
                f"  {trading_day}: sample_size {before_sample} -> {baseline.sample_size}, "
                f"stdev_return_30d {before_stdev} -> {baseline.stdev_return_30d} | {summary}"
            )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print what would change without writing to the DB")
    args = parser.parse_args()

    pool = await asyncpg.create_pool(settings.database_url)
    try:
        await run(pool, args.dry_run)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
