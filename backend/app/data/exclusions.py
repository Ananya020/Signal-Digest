"""Known data-quality exclusions: specific (ticker, date) daily-return
observations deliberately excluded from baseline/z-score computation because
they reflect a genuine corporate-action-driven price reset (a demerger,
bonus issue, or scheme of arrangement), not organic trading volatility — see
DATA_MODEL.md's "Data exclusions" section for the full investigation and the
evidence behind each entry below.

This is a documented, auditable constant that baseline computation reads
(`app/data/baselines.py::compute_baseline_from_series`) — deliberately not a
hardcoded `if ticker == ...` buried in scoring logic, so every exclusion is
visible in one place with its own reasoning, consistent with this project's
"show your work" philosophy applied to its own data pipeline, not just to
what it shows the user.

The underlying `price_ticks` row for an excluded date is NEVER deleted or
modified — it genuinely is what the ticker traded at. Only the single daily
return *attributed to* that date (see baselines.py's return-attribution
convention: return_t is attributed to day t) is excluded from every rolling
window that would otherwise include it.

Window-shifting decision (deliberately chosen, not incidental): the window
DOES reach one extra trading day further back to keep sample_size at a full
30, when real prior history exists to reach back into — it is NOT shrunk to
29 for tickers with ample history before the excluded date. This falls out
of the implementation (`compute_baseline_from_series` filters the excluded
return out of the return list, THEN takes the last 30 of what remains) but
is a deliberate choice, not an accident: an excluded date is, from the
window's perspective, exactly like a pre-existing calendar gap (a weekend, a
holiday) that this codebase has ALWAYS handled the same way — the window has
never been "the last 30 calendar days," it has always been "the last 30
valid trading-day returns," reaching back through gaps as needed. Extending
back to reuse one more REAL, already-observed trading day is not the same
kind of thing as fabricating a value (see MIN_SAMPLE_SIZE's honesty
principle below) — it's simply drawing the same window definition from one
day further back, using data that genuinely exists. Sample_size only drops
below 30 near the very start of a ticker's available history, where there
isn't a 31st real prior day to reach back into — exactly the same condition
under which sample_size already falls below 30 today for reasons unrelated
to exclusions.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DataExclusion:
    ticker: str
    excluded_date: date
    reason: str


KNOWN_EXCLUSIONS: list[DataExclusion] = [
    DataExclusion(
        ticker="TRENT.NS",
        excluded_date=date(2026, 1, 1),
        reason=(
            "-33.05% single-day move (4272.69 -> 2860.71) with BELOW-average "
            "volume (0.72x the trailing 20-day average) -- confirmed via a "
            "live yfinance re-fetch on 2026-09-06 to be a reproducible, "
            "genuine price level, not an ingestion bug (seed_historical_data.py "
            "already used auto_adjust=True; re-fetching with auto_adjust=False's "
            "Adj Close column returns the identical number). No stock split or "
            "dividend is recorded by yfinance's own actions API around this "
            "date (nearest split: 2026-06-04, unrelated). A ~33% single-day "
            "move with no corresponding volume is not consistent with organic "
            "trading (NSE circuit-breaker price bands would very likely have "
            "been breached by real unassisted trading at that magnitude); "
            "consistent instead with a bonus issue or scheme-of-arrangement "
            "price reset that yfinance's actions API doesn't track."
        ),
    ),
    DataExclusion(
        ticker="ITC.NS",
        excluded_date=date(2026, 1, 1),
        reason=(
            "-9.71% single-day move (384.26 -> 346.93) with a 34.1x volume "
            "spike -- confirmed via the same live yfinance re-fetch to be "
            "reproducible, not an ingestion bug. The combination of a large "
            "price step down plus a large volume spike is the textbook "
            "signature of a real demerger/spin-off price adjustment, which "
            "yfinance's actions API also doesn't track (it only records plain "
            "stock splits and cash dividends). Same calendar date as the "
            "TRENT.NS exclusion above; investigated and confirmed "
            "independently, not assumed to share a cause."
        ),
    ),
]


def excluded_dates_for(ticker: str) -> set[date]:
    return {e.excluded_date for e in KNOWN_EXCLUSIONS if e.ticker == ticker}
