from datetime import datetime, timedelta, timezone

from app.data.baselines import compute_baseline_as_of, compute_baseline_from_series
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


# --- Workstream 1: rolling, look-ahead-safe baseline recomputation --------


def test_compute_baseline_as_of_excludes_the_scored_day_own_move():
    # 30 flat +1% days, then day 30 (index 30) has a violent +100% move.
    # A baseline "as of" day 30 must be computed from days strictly BEFORE
    # day 30 — day 30's own huge move must not leak into its own baseline,
    # unlike compute_baseline_from_series's "as of the last point" convention.
    prices = [100.0]
    for _ in range(29):
        prices.append(prices[-1] * 1.01)
    prices.append(prices[-1] * 2.0)  # day 30: violent +100% move
    series = make_series(prices)
    as_of_date = series[30].ts.date()

    baseline = compute_baseline_as_of("X.NS", series, as_of_date)
    assert baseline is not None
    # Every return in the look-ahead-safe window is the flat ~+1% move —
    # none of them is anywhere near +100%, proving day 30 didn't leak in.
    assert baseline.mean_return_30d < 0.02
    assert baseline.stdev_5d is not None and baseline.stdev_5d < 0.01

    # Sanity check against the naive (look-ahead-UNSAFE) computation over the
    # full series, which DOES include day 30's move and is pulled up sharply.
    unsafe = compute_baseline_from_series("X.NS", series)
    assert unsafe is not None
    assert unsafe.mean_return_30d > baseline.mean_return_30d


def test_compute_baseline_as_of_returns_none_with_fewer_than_two_prior_points():
    # Only one point exists before as_of_date -> not even one return to
    # compute -> None, mirroring compute_baseline_from_series's own guard.
    series = make_series([100.0, 101.0, 102.0])
    as_of_date = series[1].ts.date()  # only series[0] is strictly before it
    assert compute_baseline_as_of("X.NS", series, as_of_date) is None


def test_sample_size_grows_as_replay_advances_then_caps_at_thirty():
    # 40 days of flat +1% history. Early "as of" days must have a smaller
    # sample_size than later ones — the confidence gate should meaningfully
    # vary across the replay sequence, not be dead code.
    prices = [100.0]
    for _ in range(39):
        prices.append(prices[-1] * 1.01)
    series = make_series(prices)

    sample_sizes = []
    for step in range(1, len(series)):
        as_of_date = series[step].ts.date()
        baseline = compute_baseline_as_of("X.NS", series, as_of_date)
        sample_sizes.append(baseline.sample_size if baseline else 0)

    # Strictly non-decreasing throughout, and strictly increasing while
    # still below the 30-day cap.
    for earlier, later in zip(sample_sizes, sample_sizes[1:]):
        assert later >= earlier
    assert sample_sizes[0] < sample_sizes[10] < 30
    # Caps at 30 once enough prior history exists (step 31 has 31 prior points -> 30 returns).
    assert sample_sizes[-1] == 30
