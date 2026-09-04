"""'Show your work' evidence — real `price_ticks` only, never fabricated.

## Correction (superseding the original Phase 3 design)

The original implementation reconstructed a 30-return window ending at the
flag's own `trading_day` and recomputed mean/stdev from *that* window
independently of the baseline actually used at scoring time. Because Phase
2's baseline is static (one row per ticker, as of the last date in its ~1y
history — see `app/data/baselines.py::load_latest_baseline`), that window
usually did not match the window the stored `z_score` was actually computed
from. The result: the displayed band (mean ± stdev) and the displayed
z_score could be mutually inconsistent — exactly the failure this screen
exists to prevent (PRODUCT.md: "auditable statistics, not black box").

**Corrected design**: `mean_return` and `stdev_return` are read directly
from the *same* baseline row (`load_latest_baseline`) that produced the
flag's stored `z_score` — never recomputed independently. The plotted
`points` window is the exact 30-return window that baseline was itself
computed from (the last 30 returns of the ticker's full real_historical
series — see `app/data/baselines.py`'s windowing convention), so the band
drawn always matches the points plotted under it. The flagged day's own
return is fetched separately (it may fall outside the baseline's window,
since the baseline is static and the flag's trading_day may be much
earlier) and is exactly the return the scoring engine computed at flag time
— so `flagged_point.z_score` (the flag's stored value) is now algebraically
reproducible as `(flagged_point.return - mean_return) / stdev_return`,
within floating-point tolerance. Tested explicitly
(`test_flagged_point_zscore_is_reproducible_from_response`).
"""

from dataclasses import dataclass

import asyncpg

from app.data.baselines import load_latest_baseline, load_price_series
from app.services.scoring import compute_return

WINDOW_SIZE = 30


class TickerMismatchError(Exception):
    """Raised when the requested flag_id does not belong to the requested ticker."""


@dataclass
class EvidencePoint:
    date: str
    return_: float
    price: float


def _baseline_window_points(series) -> list[dict]:
    """The exact last-30-returns window `load_latest_baseline`'s stats were
    computed from (see app/data/baselines.py's inclusion convention: the
    most recent day's own return is the last element of its own window)."""
    if len(series) < 2:
        return []
    start = max(0, len(series) - (WINDOW_SIZE + 1))
    window = series[start:]
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

    baseline = await load_latest_baseline(pool, ticker)
    if baseline is None or baseline.mean_return_30d is None or baseline.stdev_return_30d is None:
        return None  # nothing authoritative to display evidence against — do not fabricate

    series = await load_price_series(pool, ticker)
    points = _baseline_window_points(series)
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
