"""Baseline computation from `price_ticks` -> `baselines`, per DATA_MODEL.md.

Rolling-window inclusion convention (stated explicitly, see DATA_MODEL.md
comment on `sample_size` gating confidence):

  return_t = (close_t / close_(t-1)) - 1

`return_t` is "attributed to" day t and IS INCLUDED in any window ending at
day t — i.e. the baseline computed "as of" the most recent trading day
includes that day's own close-to-close return as the last element of the
window, not just prior days. A window of "30 return observations" therefore
requires 31 raw price observations (need t-1 for the first return in the
window). This is a deliberate choice, not an oversight: the whole point of a
baseline is "how has this stock behaved *up to and including today*", so
today's return belongs in its own baseline window.

`avg_volume_30d` is a level stat, not a return, so no such lag applies: it is
the mean of the last 30 raw daily volume observations, including the most
recent day's volume directly.

Note on schema: DATA_MODEL.md's `baselines` table has both `stdev_return_30d`
and `stdev_30d` as distinct columns with no separate raw-price-window defined
for the latter. Phase 1 treats them as the same figure (stdev of the 30-day
return window) since only one 30-day return window exists to compute from —
there is no second, differently-defined 30-day series in scope. Flagged here
rather than silently picking one and hiding the ambiguity.
"""

from dataclasses import dataclass
from datetime import date
from statistics import mean, stdev

import asyncpg

from app.providers.historical_replay import PricePoint

MIN_SAMPLE_SIZE = 20  # below this, DATA_MODEL.md says "not enough history"


@dataclass
class BaselineResult:
    ticker: str
    as_of_date: date
    mean_return_30d: float | None
    stdev_return_30d: float | None
    avg_volume_30d: float | None
    stdev_5d: float | None
    stdev_30d: float | None
    sample_size: int


def compute_baseline_from_series(ticker: str, points: list[PricePoint]) -> BaselineResult | None:
    """`points` must be chronologically sorted ascending. Baseline is computed
    as of the most recent point in the series. Returns None if there isn't
    even one prior close to compute a single return from."""
    if len(points) < 2:
        return None

    prices = [p.price for p in points]
    volumes = [p.volume for p in points]
    as_of_date = points[-1].ts.date()

    returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]

    window_30 = returns[-30:]
    window_5 = returns[-5:]
    volume_window_30 = volumes[-30:]

    sample_size = len(window_30)  # the binding "do we have enough history" gate

    return BaselineResult(
        ticker=ticker,
        as_of_date=as_of_date,
        mean_return_30d=mean(window_30) if window_30 else None,
        stdev_return_30d=stdev(window_30) if len(window_30) >= 2 else None,
        avg_volume_30d=mean(volume_window_30) if volume_window_30 else None,
        stdev_5d=stdev(window_5) if len(window_5) >= 2 else None,
        stdev_30d=stdev(window_30) if len(window_30) >= 2 else None,
        sample_size=sample_size,
    )


async def load_price_series(pool: asyncpg.Pool, ticker: str) -> list[PricePoint]:
    rows = await pool.fetch(
        """
        SELECT ts, price, volume FROM price_ticks
        WHERE ticker = $1 AND source = 'real_historical'
        ORDER BY ts ASC
        """,
        ticker,
    )
    return [PricePoint(ts=r["ts"], price=float(r["price"]), volume=r["volume"]) for r in rows]


async def upsert_baseline(pool: asyncpg.Pool, result: BaselineResult) -> None:
    await pool.execute(
        """
        INSERT INTO baselines (
            ticker, as_of_date, mean_return_30d, stdev_return_30d,
            avg_volume_30d, stdev_5d, stdev_30d, sample_size
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (ticker, as_of_date) DO UPDATE
        SET mean_return_30d = EXCLUDED.mean_return_30d,
            stdev_return_30d = EXCLUDED.stdev_return_30d,
            avg_volume_30d = EXCLUDED.avg_volume_30d,
            stdev_5d = EXCLUDED.stdev_5d,
            stdev_30d = EXCLUDED.stdev_30d,
            sample_size = EXCLUDED.sample_size
        """,
        result.ticker,
        result.as_of_date,
        result.mean_return_30d,
        result.stdev_return_30d,
        result.avg_volume_30d,
        result.stdev_5d,
        result.stdev_30d,
        result.sample_size,
    )


async def compute_and_store_baseline(pool: asyncpg.Pool, ticker: str) -> BaselineResult | None:
    series = await load_price_series(pool, ticker)
    result = compute_baseline_from_series(ticker, series)
    if result is None:
        return None
    if result.sample_size < MIN_SAMPLE_SIZE:
        # Persisted anyway (schema allows partial windows) but the low
        # sample_size is what later gates the scoring engine from flagging
        # off it — logged here so it's observable, not silently dropped.
        print(
            f"[baselines] {ticker}: sample_size={result.sample_size} "
            f"< {MIN_SAMPLE_SIZE} — insufficient history, storing as-is"
        )
    await upsert_baseline(pool, result)
    return result
