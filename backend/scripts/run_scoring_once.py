"""Manual/testable entry point for the scoring engine.

Advances the HistoricalReplayProvider's clock by N ticks (default 5) and
scores each emitted tick via app.services.scoring_pipeline.run_scoring_cycle
— the exact same function Phase 4's scheduler calls, so this script and the
live scheduler can never drift apart.

Run from backend/:
    python -m scripts.run_scoring_once [--ticks N] [--start-step S]
"""

import argparse
import asyncio

import asyncpg

from app.config import settings
from app.providers.historical_replay import HistoricalReplayProvider, ReplayClock, load_history
from app.services.scoring_pipeline import ALL_TICKERS, SECTOR_BY_NSE_TICKER, run_scoring_cycle


async def run(pool: asyncpg.Pool, num_ticks: int, start_step: int) -> None:
    history = await load_history(pool, ALL_TICKERS)

    loaded = {t: len(h) for t, h in history.items() if h}
    missing = [t for t in ALL_TICKERS if not history.get(t)]
    print(f"[run_scoring_once] loaded history for {len(loaded)}/{len(ALL_TICKERS)} tickers"
          + (f"; no data for: {missing}" if missing else ""))

    provider = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=start_step))

    flags_emitted = 0
    flags_by_signal: dict[str, int] = {}
    cycles_skipped = 0

    for _ in range(num_ticks):
        step = provider.clock.current()
        result = await run_scoring_cycle(pool, provider, ALL_TICKERS, SECTOR_BY_NSE_TICKER)

        if not result["scored"]:
            print(f"[run_scoring_once] step {step}: skipped ({result['reason']})")
            cycles_skipped += 1
            if result["reason"] == "UNAVAILABLE" or (result["reason"] or "").startswith("get_ticks_error"):
                # nothing more to do this tick, but the provider isn't
                # exhausted — still worth advancing/continuing in a real
                # scheduler; for the manual script, just move on.
                pass
            elif result["reason"] == "no_ticks":
                print(f"[run_scoring_once] step {step}: no ticks (replay exhausted)")
                break

        for flag in result["flags"]:
            flags_emitted += 1
            flags_by_signal[flag["signal_type"]] = flags_by_signal.get(flag["signal_type"], 0) + 1
            print(
                f"[run_scoring_once] FLAG {flag['ticker']} {flag['signal_type']} "
                f"severity={flag['severity']} z={flag['z_score']} "
                f"(id={flag['id']}, was_insert={flag['was_insert']}, ack_busted={flag['ack_busted']})"
            )

        provider.advance()

    print("\n=== Scoring run summary ===")
    print(f"Ticks processed: {num_ticks}")
    print(f"Flags emitted: {flags_emitted} ({flags_by_signal})")
    print(f"Cycles skipped (no scoring): {cycles_skipped}")


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
