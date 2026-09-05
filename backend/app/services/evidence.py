"""'Show your work' evidence — real `price_ticks` only, never fabricated.

## Correction (Phase 3, superseding the original design)

The original implementation reconstructed a 30-return window ending at the
flag's own `trading_day` and recomputed mean/stdev from *that* window
independently of the baseline actually used at scoring time — inconsistent
with the baseline that produced the stored `z_score`. Fixed by reading
mean/stdev directly from the same baseline row the scoring engine used.

## Correction (Workstream 1 — rolling baselines, see PROGRESS.md)

Baselines are no longer one static row per ticker; there's now a row per
(ticker, as_of_date), look-ahead-safe (`app/data/baselines.py::
compute_baseline_as_of`). Evidence must therefore fetch the baseline row for
the flag's *own* `trading_day` specifically (`load_baseline_as_of`), not
merely "whatever's most recently computed" (`load_latest_baseline`, which
would now return a different, later ticker's baseline than the one that
actually produced this flag's z_score). Likewise, the plotted `points`
window is reconstructed using the same look-ahead-safe cutoff (only prices
strictly before `trading_day`), so the band drawn still matches both the
points plotted under it and the baseline row used to score the flag.

The flagged day's own return is fetched separately (its date is excluded
from its own baseline's window by construction) and is exactly the return
the scoring engine computed at flag time — so `flagged_point.z_score` (the
flag's stored value) remains algebraically reproducible as
`(flagged_point.return - mean_return) / stdev_return`, within
floating-point tolerance. Tested explicitly
(`test_flagged_point_zscore_is_reproducible_from_response`).
"""

from dataclasses import dataclass
from datetime import date

import asyncpg

from app.data.baselines import load_baseline_as_of, load_price_series
from app.services.scoring import compute_return

WINDOW_SIZE = 30


class TickerMismatchError(Exception):
    """Raised when the requested flag_id does not belong to the requested ticker."""


@dataclass
class EvidencePoint:
    date: str
    return_: float
    price: float


def _baseline_window_points(series, as_of_date: date) -> list[dict]:
    """The exact last-30-returns window `compute_baseline_as_of(as_of_date)`
    computed its stats from: only points strictly before `as_of_date`,
    look-ahead-safe, matching the rolling baseline's own windowing."""
    prior_series = [p for p in series if p.ts.date() < as_of_date]
    if len(prior_series) < 2:
        return []
    start = max(0, len(prior_series) - (WINDOW_SIZE + 1))
    window = prior_series[start:]
    return [
        {
            "date": window[i].ts.date().isoformat(),
            "return": compute_return(window[i - 1].price, window[i].price),
            "price": window[i].price,
        }
        for i in range(1, len(window))
    ]


async def build_evidence(pool: asyncpg.Pool, ticker: str, flag_id: int) -> dict | None:
    flag = await pool.fetchrow(
        "SELECT id, ticker, trading_day, z_score FROM flags WHERE id = $1", flag_id
    )
    if flag is None:
        return None

    if flag["ticker"] != ticker:
        raise TickerMismatchError(f"flag {flag_id} belongs to {flag['ticker']}, not {ticker}")

    baseline = await load_baseline_as_of(pool, ticker, flag["trading_day"])
    if baseline is None or baseline.mean_return_30d is None or baseline.stdev_return_30d is None:
        return None  # nothing authoritative to display evidence against — do not fabricate

    series = await load_price_series(pool, ticker)
    points = _baseline_window_points(series, flag["trading_day"])
    if not points:
        return None

    idx = next((i for i, p in enumerate(series) if p.ts.date() == flag["trading_day"]), None)
    if idx is None or idx == 0:
        # No matching historical price for this trading_day, or nothing
        # precedes it to compute even one return from — do not fabricate.
        return None
    flagged_return = compute_return(series[idx - 1].price, series[idx].price)

    flagged_point = {
        "date": flag["trading_day"].isoformat(),
        "return": flagged_return,
        "z_score": float(flag["z_score"]) if flag["z_score"] is not None else None,
    }

    return {
        "ticker": ticker,
        "window_start": points[0]["date"],
        "window_end": points[-1]["date"],
        "mean_return": baseline.mean_return_30d,
        "stdev_return": baseline.stdev_return_30d,
        "points": points,
        "flagged_point": flagged_point,
    }
