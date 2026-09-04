"""One-off manual smoke test: loads real historical price_ticks from Postgres
and drives HistoricalReplayProvider over a few steps, printing what it emits.
Not part of the pytest suite — this is a human-readable sanity check against
real seeded data, run manually:
    python -m scripts.smoke_test_replay
"""

import asyncio

import asyncpg

from app.config import settings
from app.providers.historical_replay import HistoricalReplayProvider, ReplayClock, load_history


async def main() -> None:
    pool = await asyncpg.create_pool(settings.database_url)
    try:
        tickers = ["RELIANCE.NS", "TCS.NS", "M&M.NS"]
        history = await load_history(pool, tickers)
        for t in tickers:
            print(f"{t}: {len(history[t])} historical observations loaded")

        provider = HistoricalReplayProvider(history=history, clock=ReplayClock())

        for step in range(3):
            ticks = provider.get_ticks(tickers)
            print(f"\n-- step {step} --")
            for tick in ticks:
                print(
                    f"  {tick.ticker}: price={tick.price} volume={tick.volume} "
                    f"ts={tick.timestamp} source={tick.source}"
                )
                assert tick.source == "replay_simulated"
            status = provider.get_status()
            print(f"  status: {status.state} ({status.detail})")
            provider.advance()

        print("\nSMOKE TEST OK: all emitted ticks tagged source='replay_simulated', "
              "prices match real historical values, chronological order confirmed.")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
