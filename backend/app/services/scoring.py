"""Deterministic scoring engine — no ML, no composite weighted score, per
PRODUCT.md. Price z-score is the sole trigger for `price_zscore` flags;
volume ratio and sector-relative tag are annotations attached to that flag,
never folded into it. `volatility_regime` is a separate, secondary signal.

Severity band convention (resolves the boundary notation in the spec, which
gives overlapping-looking ranges "notable 2.0-2.5 / significant 2.5-3.5 /
extreme >3.5"): each band's *lower* bound is inclusive, so a boundary value
belongs to the band it opens — 2.0 is notable, 2.5 is significant, 3.5 is
extreme. This is consistent with the stated trigger "flag if |z| >= 2.0".
"""

from dataclasses import dataclass
from datetime import date, datetime
from statistics import mean
from zoneinfo import ZoneInfo

from app.data.baselines import MIN_SAMPLE_SIZE, BaselineResult
from app.providers.base import Tick

IST = ZoneInfo("Asia/Kolkata")

Z_SCORE_TRIGGER = 2.0
SEVERITY_BANDS: list[tuple[float, str, int]] = [
    (3.5, "extreme", 3),
    (2.5, "significant", 2),
    (2.0, "notable", 1),
]

VOLATILITY_REGIME_TRIGGER = 1.5
# Spec gives only the trigger threshold for volatility_regime, not severity
# bands. Documented judgment call: scale the same relative-jump idea onto
# three bands so the flags table's NOT NULL severity/severity_rank columns
# always have a real value, never a fabricated placeholder.
VOLATILITY_SEVERITY_BANDS: list[tuple[float, str, int]] = [
    (3.0, "extreme", 3),
    (2.0, "significant", 2),
    (1.5, "notable", 1),
]

# Judgment call, documented: "sector_wide" requires the sector's other
# members to have moved, on average, in the same direction and to at least
# half the magnitude of the flagged stock's own move. PRODUCT.md specifies
# the comparison exists as an annotation but not an exact formula.
SECTOR_WIDE_RATIO_THRESHOLD = 0.5
MIN_SECTOR_PEERS_WITH_DATA = 2


@dataclass
class FlagCandidate:
    ticker: str
    trading_day: date
    signal_type: str  # 'price_zscore' | 'volatility_regime'
    z_score: float | None
    severity: str
    severity_rank: int
    volume_ratio: float | None
    sector_relative: str | None
    computed_at: datetime
    provider_state_at_computation: str


def trading_day_from_tick(tick: Tick) -> date:
    """The historical date the replayed tick actually corresponds to — never
    wall-clock 'today'. Replay ticks come from real past dates; using
    datetime.now() here would collide every ticker's entire history onto one
    date and violate UNIQUE(ticker, trading_day, signal_type) in confusing
    ways.

    Correction (RELIABILITY.md #10, caught by test before it shipped as a
    live bug): `tick.timestamp` is UTC-aware; taking `.date()` directly
    gives the UTC calendar date, not the Asia/Kolkata trading day. The two
    only coincide when the tick falls well inside the IST day — which is
    why real seeded data (anchored at 15:30 IST = 10:00 UTC, comfortably
    mid-day) never surfaced this. A tick near the UTC/IST day boundary
    would silently bucket into the wrong trading_day otherwise. Convert to
    IST explicitly before taking the date, per RELIABILITY.md's design
    ("all timestamps UTC internally, trading-day boundaries computed in
    Asia/Kolkata explicitly")."""
    return tick.timestamp.astimezone(IST).date()


def compute_return(prev_price: float, curr_price: float) -> float:
    return curr_price / prev_price - 1


def z_score(today_return: float, mean_return: float | None, stdev_return: float | None) -> float | None:
    if stdev_return is None or stdev_return == 0 or mean_return is None:
        return None  # abstain rather than divide by zero
    return (today_return - mean_return) / stdev_return


def severity_band(abs_z: float, bands: list[tuple[float, str, int]] = SEVERITY_BANDS) -> tuple[str, int] | None:
    for threshold, label, rank in bands:
        if abs_z >= threshold:
            return label, rank
    return None


def volume_ratio(today_volume: int | None, avg_volume_30d: float | None) -> float | None:
    """None (unknown) for missing/zero volume or missing baseline — a
    zero-volume day (e.g. M&M.NS 2025-09-08 in the real seeded data) must
    read as 'no corroborating signal available', not as '0x volume', which
    would look like a deliberate anomaly."""
    if not today_volume or not avg_volume_30d:
        return None
    return today_volume / avg_volume_30d


def volatility_regime_ratio(stdev_5d: float | None, stdev_30d: float | None) -> float | None:
    if not stdev_30d or stdev_5d is None:
        return None
    return stdev_5d / stdev_30d


def sector_relative_tag(ticker_return: float, peer_returns: list[float]) -> str | None:
    """NULL when fewer than MIN_SECTOR_PEERS_WITH_DATA peers have a valid
    tick this cycle — never computed off partial sector data."""
    if len(peer_returns) < MIN_SECTOR_PEERS_WITH_DATA:
        return None
    sector_mean = mean(peer_returns)
    if ticker_return == 0:
        return "stock_specific"
    same_sign = (sector_mean > 0) == (ticker_return > 0)
    if same_sign and abs(sector_mean) >= SECTOR_WIDE_RATIO_THRESHOLD * abs(ticker_return):
        return "sector_wide"
    return "stock_specific"


def score_price_zscore(
    *,
    ticker: str,
    trading_day: date,
    today_return: float,
    today_volume: int | None,
    baseline: BaselineResult,
    peer_returns: list[float],
    computed_at: datetime,
    provider_state: str,
) -> FlagCandidate | None:
    if baseline.sample_size < MIN_SAMPLE_SIZE:
        print(f"[scoring] {ticker} {trading_day}: sample_size={baseline.sample_size} "
              f"< {MIN_SAMPLE_SIZE} — insufficient history, suppressing price_zscore flag")
        return None

    z = z_score(today_return, baseline.mean_return_30d, baseline.stdev_return_30d)
    if z is None:
        return None

    band = severity_band(abs(z))
    if band is None:
        return None
    severity, rank = band

    return FlagCandidate(
        ticker=ticker,
        trading_day=trading_day,
        signal_type="price_zscore",
        z_score=z,
        severity=severity,
        severity_rank=rank,
        volume_ratio=volume_ratio(today_volume, baseline.avg_volume_30d),
        sector_relative=sector_relative_tag(today_return, peer_returns),
        computed_at=computed_at,
        provider_state_at_computation=provider_state,
    )


def score_volatility_regime(
    *,
    ticker: str,
    trading_day: date,
    baseline: BaselineResult,
    computed_at: datetime,
    provider_state: str,
) -> FlagCandidate | None:
    if baseline.sample_size < MIN_SAMPLE_SIZE:
        print(f"[scoring] {ticker} {trading_day}: sample_size={baseline.sample_size} "
              f"< {MIN_SAMPLE_SIZE} — insufficient history, suppressing volatility_regime flag")
        return None

    ratio = volatility_regime_ratio(baseline.stdev_5d, baseline.stdev_30d)
    if ratio is None or ratio < VOLATILITY_REGIME_TRIGGER:
        return None

    band = severity_band(ratio, VOLATILITY_SEVERITY_BANDS)
    if band is None:
        return None
    severity, rank = band

    return FlagCandidate(
        ticker=ticker,
        trading_day=trading_day,
        signal_type="volatility_regime",
        z_score=None,  # not a price z-score; no fabricated value here
        severity=severity,
        severity_rank=rank,
        volume_ratio=None,  # volume is not part of this signal's definition
        sector_relative=None,  # sector comparison is defined for price moves, not volatility regime
        computed_at=computed_at,
        provider_state_at_computation=provider_state,
    )
