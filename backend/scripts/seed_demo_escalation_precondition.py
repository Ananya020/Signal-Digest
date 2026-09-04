"""Seeds a CONSTRUCTED precondition for the Phase 4 live demo's
severity-escalation-flip beat — nothing more.

## Why this script exists

Under this project's daily-close historical replay, `(ticker, trading_day,
signal_type)` scores deterministically: the same close price and the same
static baseline (Phase 2) produce the same z_score and severity every time
that day is scored, no matter when. There is no legitimate way for the
*same* trading day to organically escalate to a higher severity on a later
re-score — that would require either the underlying return or the baseline
to change, and neither does for a fixed historical day. A real intraday
feed (multiple ticks arriving through a single trading session) WOULD
exhibit genuine escalation, since the day's return keeps changing as new
ticks arrive; this replay's one-close-per-day granularity does not have
that intraday texture. See PROGRESS.md / RELIABILITY.md for the full
architectural note.

## What this script does — and does NOT do

It inserts ONE flag row for a specific real ticker and a specific real
trading_day that the live replay has NOT yet reached, at an artificially
LOW severity (standing in for "assessed before full information was
available" — the exact premise of RELIABILITY.md scenario #3), and
acknowledges it.

That is the ENTIRE extent of what's constructed. Nothing about the scoring
engine, the ack-bust upsert, or the transaction logic is touched or
special-cased here — none of that code is even imported by this script. When
the live scheduler's replay position naturally reaches the seeded
trading_day, it re-scores that real day from real `price_ticks` and the
real stored baseline, using the exact same `run_scoring_cycle` /
`upsert_flag_with_ack_bust` code Phase 2/3 already verified. If the
genuinely-computed severity for that day is higher than the artificially
seeded one (which this script verifies BEFORE seeding, using the real
scoring functions — it will refuse to seed a placeholder that wouldn't
actually be superseded), the resulting ack-bust is entirely real,
scheduler-driven, and computed by the unmodified engine from real data.

## Requires a manual run — never invoked automatically

Not imported by run_scoring_once.py, the scheduler, or app startup. Run
explicitly, once, before the demo:

    python -m scripts.seed_demo_escalation_precondition --ticker POWERGRID.NS \\
        --trading-day 2026-02-16 --watchlist-id <uuid> [--placeholder-severity notable]
"""

import argparse
import asyncio
from datetime import date, datetime, timezone

import asyncpg

from app.config import settings
from app.data.baselines import load_latest_baseline
from app.data.tickers import to_nse_symbol
from app.providers.historical_replay import load_history
from app.services.scoring import compute_return, severity_band, z_score

PLACEHOLDER_SEVERITY_BY_RANK = {1: "notable", 2: "significant", 3: "extreme"}


async def verify_and_seed(
    pool: asyncpg.Pool,
    ticker: str,
    trading_day: date,
    watchlist_id: str,
    placeholder_rank: int,
) -> None:
    baseline = await load_latest_baseline(pool, ticker)
    if baseline is None:
        raise SystemExit(f"No baseline for {ticker} — cannot verify the real severity ahead of time.")

    history = await load_history(pool, [ticker])
    series = history[ticker]
    idx = next((i for i, p in enumerate(series) if p.ts.date() == trading_day), None)
    if idx is None or idx == 0:
        raise SystemExit(f"{ticker} has no real_historical price for {trading_day} (or no prior close).")

    real_return = compute_return(series[idx - 1].price, series[idx].price)
    real_z = z_score(real_return, baseline.mean_return_30d, baseline.stdev_return_30d)
    if real_z is None:
        raise SystemExit("Real z_score could not be computed (zero/missing stdev) — refusing to seed.")
    real_band = severity_band(abs(real_z))
    if real_band is None:
        raise SystemExit(f"Real |z|={abs(real_z):.3f} does not even cross the notable trigger — nothing to escalate to.")
    real_severity, real_rank = real_band

    print(f"[seed] Verified real (engine-computed) outcome for {ticker} on {trading_day}: "
          f"z={real_z:.3f}, severity={real_severity} (rank {real_rank})")

    if placeholder_rank >= real_rank:
        raise SystemExit(
            f"Placeholder rank {placeholder_rank} is not lower than the real rank {real_rank} — "
            "this would not produce an escalation. Choose a lower --placeholder-severity or a different ticker/day."
        )

    placeholder_severity = PLACEHOLDER_SEVERITY_BY_RANK[placeholder_rank]

    print(
        f"[seed] Seeding a CONSTRUCTED precondition: {ticker} {trading_day} price_zscore "
        f"at severity={placeholder_severity} (rank {placeholder_rank}) — this is NOT a real computed "
        f"value, it stands in for 'assessed before full information was available' "
        f"(RELIABILITY.md scenario #3). The real value ({real_severity}, rank {real_rank}) will "
        f"supersede it the moment the live scheduler's replay position naturally reaches this day."
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO flags (
                ticker, trading_day, signal_type, z_score, severity, severity_rank,
                volume_ratio, sector_relative, computed_at, provider_state_at_computation
            )
            VALUES ($1, $2, 'price_zscore', $3, $4, $5, NULL, NULL, now(), 'replay_simulated')
            ON CONFLICT (ticker, trading_day, signal_type) DO UPDATE
            SET z_score = EXCLUDED.z_score, severity = EXCLUDED.severity, severity_rank = EXCLUDED.severity_rank,
                computed_at = EXCLUDED.computed_at, provider_state_at_computation = EXCLUDED.provider_state_at_computation
            RETURNING id
            """,
            ticker, trading_day, 2.1, placeholder_severity, placeholder_rank,
        )
        flag_id = row["id"]
        await conn.execute(
            "INSERT INTO flag_ack (flag_id, watchlist_id, acked_at) VALUES ($1, $2, now()) "
            "ON CONFLICT (flag_id, watchlist_id) DO NOTHING",
            flag_id, watchlist_id,
        )

    print(f"[seed] Done. flag_id={flag_id}, acked on watchlist {watchlist_id}.")
    print(f"[seed] Expect: once the live replay reaches {trading_day} for {ticker}, this flag should "
          f"reappear UNACKNOWLEDGED at severity={real_severity} (rank {real_rank}).")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True, help="Bare or .NS-suffixed symbol, e.g. POWERGRID or POWERGRID.NS")
    parser.add_argument("--trading-day", required=True, help="YYYY-MM-DD, a real day the replay has not yet reached")
    parser.add_argument("--watchlist-id", required=True, help="UUID of an existing watchlist containing this ticker")
    parser.add_argument("--placeholder-severity", default="notable", choices=["notable", "significant"])
    args = parser.parse_args()

    ticker = args.ticker if args.ticker.endswith(".NS") else to_nse_symbol(args.ticker)
    trading_day = datetime.strptime(args.trading_day, "%Y-%m-%d").date()
    placeholder_rank = {"notable": 1, "significant": 2}[args.placeholder_severity]

    pool = await asyncpg.create_pool(settings.database_url)
    try:
        await verify_and_seed(pool, ticker, trading_day, args.watchlist_id, placeholder_rank)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
