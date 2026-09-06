from datetime import date, datetime, timezone

from app.data.baselines import BaselineResult
from app.services.scoring import (
    score_price_zscore,
    score_volatility_regime,
    sector_relative_tag,
    severity_band,
    trading_day_from_tick,
    volume_ratio,
    z_score,
)
from app.providers.base import Tick


def make_baseline(**overrides) -> BaselineResult:
    defaults = dict(
        ticker="X.NS",
        as_of_date=date(2026, 1, 1),
        mean_return_30d=0.0,
        stdev_return_30d=0.02,
        avg_volume_30d=1_000_000.0,
        stdev_5d=0.02,
        stdev_30d=0.02,
        sample_size=30,
    )
    defaults.update(overrides)
    return BaselineResult(**defaults)


# ---- z-score ----

def test_z_score_known_values():
    # return 6% above a 0% mean, stdev 2% -> z = 3.0
    assert round(z_score(0.06, 0.0, 0.02), 6) == 3.0


def test_z_score_zero_stdev_abstains_no_divide_by_zero():
    assert z_score(0.10, 0.0, 0.0) is None


def test_z_score_missing_stdev_abstains():
    assert z_score(0.10, 0.0, None) is None


# ---- severity bands ----

def test_severity_band_boundaries():
    assert severity_band(2.0) == ("notable", 1)
    assert severity_band(2.4999) == ("notable", 1)
    assert severity_band(2.5) == ("significant", 2)
    assert severity_band(3.4999) == ("significant", 2)
    assert severity_band(3.5) == ("extreme", 3)
    assert severity_band(1.999) is None  # below trigger, not flagged at all


# ---- volume ratio ----

def test_volume_ratio_normal_case():
    assert round(volume_ratio(2_000_000, 1_000_000.0), 2) == 2.0


def test_volume_ratio_none_when_volume_missing():
    assert volume_ratio(None, 1_000_000.0) is None


def test_volume_ratio_none_when_volume_zero_not_read_as_0x():
    # Real case from Phase 1 seeded data: M&M.NS 2025-09-08 had volume=0.
    assert volume_ratio(0, 1_000_000.0) is None


def test_volume_ratio_none_when_baseline_avg_missing():
    assert volume_ratio(500_000, None) is None


# ---- confidence gate ----

def test_confidence_gate_suppresses_price_zscore_flag_below_min_sample_size():
    baseline = make_baseline(sample_size=15)
    result = score_price_zscore(
        ticker="X.NS", trading_day=date(2026, 1, 1), today_return=0.10,
        today_volume=1_000_000, baseline=baseline, peer_returns=[],
        computed_at=datetime.now(timezone.utc), provider_state="replay_simulated",
    )
    assert result is None


def test_confidence_gate_suppresses_volatility_regime_flag_below_min_sample_size():
    baseline = make_baseline(sample_size=10, stdev_5d=0.05, stdev_30d=0.02)
    result = score_volatility_regime(
        ticker="X.NS", trading_day=date(2026, 1, 1), baseline=baseline,
        computed_at=datetime.now(timezone.utc), provider_state="replay_simulated",
    )
    assert result is None


def test_known_data_exclusion_suppresses_price_zscore_flag_regardless_of_how_extreme():
    # TRENT.NS/2026-01-01 is a real KNOWN_EXCLUSIONS entry (app/data/exclusions.py).
    # An extreme return here must never produce a flag, no matter how large.
    baseline = make_baseline(sample_size=30)
    result = score_price_zscore(
        ticker="TRENT.NS", trading_day=date(2026, 1, 1), today_return=-0.90,
        today_volume=1_000_000, baseline=baseline, peer_returns=[],
        computed_at=datetime.now(timezone.utc), provider_state="real_historical",
    )
    assert result is None


def test_known_data_exclusion_suppresses_volatility_regime_flag_regardless_of_ratio():
    baseline = make_baseline(sample_size=30, stdev_5d=1.0, stdev_30d=0.02)
    result = score_volatility_regime(
        ticker="ITC.NS", trading_day=date(2026, 1, 1), baseline=baseline,
        computed_at=datetime.now(timezone.utc), provider_state="real_historical",
    )
    assert result is None


def test_known_data_exclusion_only_suppresses_the_exact_excluded_ticker_and_date():
    baseline = make_baseline(sample_size=30)
    # Same ticker, different day -> not suppressed.
    result_other_day = score_price_zscore(
        ticker="TRENT.NS", trading_day=date(2026, 1, 2), today_return=-0.90,
        today_volume=1_000_000, baseline=baseline, peer_returns=[],
        computed_at=datetime.now(timezone.utc), provider_state="real_historical",
    )
    assert result_other_day is not None

    # Same day, different (non-excluded) ticker -> not suppressed.
    result_other_ticker = score_price_zscore(
        ticker="RELIANCE.NS", trading_day=date(2026, 1, 1), today_return=-0.90,
        today_volume=1_000_000, baseline=baseline, peer_returns=[],
        computed_at=datetime.now(timezone.utc), provider_state="real_historical",
    )
    assert result_other_ticker is not None


def test_price_zscore_flag_emitted_when_sample_size_sufficient():
    baseline = make_baseline(sample_size=30)
    result = score_price_zscore(
        ticker="X.NS", trading_day=date(2026, 1, 1), today_return=0.10,
        today_volume=1_000_000, baseline=baseline, peer_returns=[],
        computed_at=datetime.now(timezone.utc), provider_state="replay_simulated",
    )
    assert result is not None
    assert result.signal_type == "price_zscore"


# ---- sector tag ----

def test_sector_tag_null_when_fewer_than_two_peers():
    assert sector_relative_tag(0.05, []) is None
    assert sector_relative_tag(0.05, [0.04]) is None


def test_sector_tag_sector_wide_when_peers_move_same_direction_similar_magnitude():
    # ticker +6%, peers averaging +4% (>= 0.5 * 6% = 3%) -> sector_wide
    assert sector_relative_tag(0.06, [0.03, 0.05]) == "sector_wide"


def test_sector_tag_stock_specific_when_peers_flat_or_opposite():
    assert sector_relative_tag(0.06, [0.001, -0.002]) == "stock_specific"
    assert sector_relative_tag(0.06, [-0.05, -0.04]) == "stock_specific"


# ---- trading_day from replay tick, never wall-clock ----

def test_trading_day_uses_historical_tick_date_not_wallclock_today():
    historical_ts = datetime(2025, 9, 4, 10, 0, tzinfo=timezone.utc)
    tick = Tick(ticker="X.NS", price=100.0, volume=1000, timestamp=historical_ts, source="replay_simulated")
    trading_day = trading_day_from_tick(tick)
    assert trading_day == date(2025, 9, 4)
    assert trading_day != date.today()
