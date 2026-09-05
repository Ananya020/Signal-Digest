"""Read-only helper for the E2E demo-rehearsal test — finds the NEAREST real
(ticker, trading_day) pair, strictly after --min-step, whose engine-computed
severity crosses a given threshold. Never writes anything; computes via the
exact same look-ahead-safe functions the live scoring pipeline uses
(`compute_baseline_as_of`, `z_score`, `severity_band`) so its answer is
guaranteed to match what `run_scoring_cycle` will really produce once
replay reaches that day — the same guarantee
`seed_demo_escalation_precondition.py` already relies on.

Exists because the escalation-flip demo beat needs a real future day that
crosses the trigger, and which one qualifies depends on where the live
server's replay clock currently is (unknown until the server is already
running) — this can't be hardcoded once and reused as a fixture.

Prints one JSON line to stdout:
    {"ticker": "...", "trading_day": "YYYY-MM-DD", "z": 3.67,
     "severity": "extreme", "severity_rank": 3, "step": 20}
or `null` if nothing qualifies within the scanned range.

    python -m scripts.find_escalation_candidate --min-step 5 [--min-severity-rank 3] [--tickers A.NS B.NS]
"""

import argparse
import asyncio
import json

import asyncpg

from app.config import settings
from app.data.baselines import MIN_SAMPLE_SIZE, compute_baseline_as_of
from app.providers.historical_replay import load_history
from app.services.scoring import compute_return, severity_band, z_score
from app.services.scoring_pipeline import ALL_TICKERS


async def find_candidate(min_step: int, min_severity_rank: int, tickers: list[str]) -> dict | None:
    pool = await asyncpg.create_pool(settings.database_url)
    try:
        history = await load_history(pool, tickers)
        best: dict | None = None
        for ticker, series in history.items():
            for idx in range(max(min_step + 1, 1), len(series)):
                if best is not None and idx >= best["step"]:
                    break  # already have a strictly earlier candidate; later days on this ticker can't beat it
                day = series[idx].ts.date()
                baseline = compute_baseline_as_of(ticker, series, day)
                if baseline is None:
                    continue
                if baseline.sample_size < MIN_SAMPLE_SIZE:
                    # Must match score_price_zscore()'s own confidence gate
                    # exactly — a day the real pipeline would suppress can
                    # never be a valid escalation-flip target (the seeded
                    # placeholder would never actually get corrected).
                    continue
                ret = compute_return(series[idx - 1].price, series[idx].price)
                z = z_score(ret, baseline.mean_return_30d, baseline.stdev_return_30d)
                if z is None:
                    continue
                band = severity_band(abs(z))
                if band is None:
                    continue
                severity, rank = band
                if rank < min_severity_rank:
                    continue
                if best is None or idx < best["step"]:
                    best = {
                        "ticker": ticker,
                        "trading_day": day.isoformat(),
                        "z": round(z, 3),
                        "severity": severity,
                        "severity_rank": rank,
                        "step": idx,
                    }
        return best
    finally:
        await pool.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-step", type=int, required=True)
    parser.add_argument("--min-severity-rank", type=int, default=2, choices=[1, 2, 3])
    parser.add_argument("--tickers", nargs="*", default=None)
    args = parser.parse_args()

    result = await find_candidate(args.min_step, args.min_severity_rank, args.tickers or ALL_TICKERS)
    print(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
