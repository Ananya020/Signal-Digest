"""Manual/testable entry point for Phase 2's scoring engine.

Advances the HistoricalReplayProvider's clock by N ticks (default 5) and
scores each emitted tick, persisting flags via the ack-bust-safe upsert.

Deliberately NOT a background scheduler. APScheduler-driven continuous
ingestion is Phase 3/4 territory, once the API and /admin/fault need a live
running process (see PROGRESS.md). Keeping Phase 2 to a manual, directly
invokable script keeps the scoring math and the ack-bust transaction the
only things under test here — no scheduler concurrency to debug alongside.

Run from backend/:
    python -m scripts.run_scoring_once [--ticks N] [--start-step S]
"""

import argparse
import asyncio
from datetime import datetime, timezone

import asyncpg

from app.config import settings
from app.data.baselines import load_latest_baseline
from app.data.tickers import TICKER_SECTORS, to_nse_symbol
from app.providers.historical_replay import HistoricalReplayProvider, ReplayClock, load_history
from app.services.flags import upsert_flag_with_ack_bust
from app.services.scoring import (
    compute_return,
    score_price_zscore,
    score_volatility_regime,
    trading_day_from_tick,
)

SECTOR_BY_NSE_TICKER = {to_nse_symbol(bare): sector for bare, sector in TICKER_SECTORS.items()}


async def run(pool: asyncpg.Pool, num_ticks: int, start_step: int) -> None:
    tickers = list(SECTOR_BY_NSE_TICKER.keys())
    history = await load_history(pool, tickers)

    loaded = {t: len(h) for t, h in history.items() if h}
    missing = [t for t in tickers if not history.get(t)]
    print(f"[run_scoring_once] loaded history for {len(loaded)}/{len(tickers)} tickers"
          + (f"; no data for: {missing}" if missing else ""))

    provider = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=start_step))

    flags_emitted = 0
    flags_by_signal: dict[str, int] = {}
    skipped_first_day = 0
    skipped_no_baseline = 0

    async with pool.acquire() as conn:
        for _ in range(num_ticks):
            step = provider.clock.current()
            ticks = provider.get_ticks(tickers)
            if not ticks:
                print(f"[run_scoring_once] step {step}: no ticks (replay exhausted)")
                break

            # Today's return needs yesterday's close from the same series;
            # not available for the very first replayed day.
            today_returns: dict[str, float] = {}
            for tick in ticks:
                series = history[tick.ticker]
                if step == 0:
                    continue
                prev_price = series[step - 1].price
                today_returns[tick.ticker] = compute_return(prev_price, tick.price)

            if step == 0:
                skipped_first_day += len(ticks)
                provider.advance()
                continue

            for tick in ticks:
                if tick.ticker not in today_returns:
                    continue
                baseline = await load_latest_baseline(pool, tick.ticker)
                if baseline is None:
                    skipped_no_baseline += 1
                    continue

                trading_day = trading_day_from_tick(tick)
                sector = SECTOR_BY_NSE_TICKER[tick.ticker]
                peer_returns = [
                    r for t, r in today_returns.items()
                    if t != tick.ticker and SECTOR_BY_NSE_TICKER.get(t) == sector
                ]

                candidates = []
                price_flag = score_price_zscore(
                    ticker=tick.ticker,
                    trading_day=trading_day,
                    today_return=today_returns[tick.ticker],
                    today_volume=tick.volume,
                    baseline=baseline,
                    peer_returns=peer_returns,
                    computed_at=datetime.now(timezone.utc),
                    provider_state=tick.source,
                )
                if price_flag:
                    candidates.append(price_flag)

                vol_flag = score_volatility_regime(
                    ticker=tick.ticker,
                    trading_day=trading_day,
                    baseline=baseline,
                    computed_at=datetime.now(timezone.utc),
                    provider_state=tick.source,
                )
                if vol_flag:
                    candidates.append(vol_flag)

                for candidate in candidates:
                    result = await upsert_flag_with_ack_bust(conn, candidate)
                    flags_emitted += 1
                    flags_by_signal[candidate.signal_type] = flags_by_signal.get(candidate.signal_type, 0) + 1
                    print(
                        f"[run_scoring_once] FLAG {candidate.ticker} {candidate.trading_day} "
                        f"{candidate.signal_type} severity={candidate.severity} "
                        f"z={candidate.z_score} vol_ratio={candidate.volume_ratio} "
                        f"sector={candidate.sector_relative} "
                        f"(id={result.id}, was_insert={result.was_insert}, ack_busted={result.ack_busted})"
                    )

            provider.advance()

    print("\n=== Scoring run summary ===")
    print(f"Ticks processed: {num_ticks}")
    print(f"Flags emitted: {flags_emitted} ({flags_by_signal})")
    print(f"Skipped (first replay day, no prior close for return calc): {skipped_first_day}")
    print(f"Skipped (no baseline row for ticker): {skipped_no_baseline}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=int, default=5)
    parser.add_argument("--start-step", type=int, default=1)  # step 0 has no prior close
    args = parser.parse_args()

    pool = await asyncpg.create_pool(settings.database_url)
    try:
        await run(pool, args.ticks, args.start_step)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
