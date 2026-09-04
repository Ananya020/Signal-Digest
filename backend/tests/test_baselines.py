from datetime import datetime, timedelta, timezone

from app.data.baselines import compute_baseline_from_series
from app.providers.historical_replay import PricePoint


def make_series(prices: list[float], volumes: list[int] | None = None) -> list[PricePoint]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    volumes = volumes or [1000] * len(prices)
    return [
        PricePoint(ts=start + timedelta(days=i), price=p, volume=v)
        for i, (p, v) in enumerate(zip(prices, volumes))
    ]


def test_insufficient_history_returns_none_not_fabricated():
    # A single price point can't produce even one return.
    assert compute_baseline_from_series("X.NS", make_series([100.0])) is None
    assert compute_baseline_from_series("X.NS", []) is None


def test_return_calculation_correctness():
    # 100 -> 110 -> 99: returns are +10% then -10%.
    series = make_series([100.0, 110.0, 99.0])
    result = compute_baseline_from_series("X.NS", series)
    assert result is not None
    assert result.sample_size == 2
    assert round(result.mean_return_30d, 6) == round((0.10 + (-0.10)) / 2, 6)


def test_sample_size_caps_at_window_even_with_more_history():
    # 40 price points -> 39 returns, but the 30-day window caps sample_size at 30.
    series = make_series([100.0 + i for i in range(40)])
    result = compute_baseline_from_series("X.NS", series)
    assert result is not None
    assert result.sample_size == 30


def test_stdev_5d_uses_last_five_returns_only():
    # Constant +1% returns for the first 34 days, then a single volatile day.
    prices = [100.0]
    for _ in range(34):
        prices.append(prices[-1] * 1.01)
    prices.append(prices[-1] * 1.50)  # sharp final-day move
    series = make_series(prices)
    result = compute_baseline_from_series("X.NS", series)
    assert result is not None
    # stdev_5d must be materially larger than a stdev computed only over the
    # flat 1% stretch, since the volatile final return falls inside the last-5 window.
    assert result.stdev_5d is not None and result.stdev_5d > 0.05


def test_avg_volume_30d_is_mean_of_last_30_raw_volumes():
    volumes = [1000] * 40
    volumes[-1] = 5000  # most recent day's volume spikes
    series = make_series([100.0 + i for i in range(40)], volumes)
    result = compute_baseline_from_series("X.NS", series)
    assert result is not None
    expected = (1000 * 29 + 5000) / 30
    assert round(result.avg_volume_30d, 2) == round(expected, 2)


def test_current_day_return_included_in_its_own_window():
    # Documents the stated inclusion convention: the as-of day's own return
    # is the LAST element of the window, not excluded from it.
    series = make_series([100.0, 100.0, 200.0])  # last return is +100%
    result = compute_baseline_from_series("X.NS", series)
    assert result is not None
    assert result.mean_return_30d > 0.4  # the +100% day pulls the mean up sharply
