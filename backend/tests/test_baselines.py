from datetime import date, datetime, timedelta, timezone

from app.data.baselines import compute_baseline_as_of, compute_baseline_from_series
from app.data.exclusions import DataExclusion, KNOWN_EXCLUSIONS, excluded_dates_for
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


# --- Deployment-prep correction: known data exclusions (app/data/exclusions.py) --


def _points_with_dates(dated_prices: list[tuple[date, float]]) -> list[PricePoint]:
    return [
        PricePoint(ts=datetime(d.year, d.month, d.day, 10, tzinfo=timezone.utc), price=p, volume=1000)
        for d, p in dated_prices
    ]


def test_excluded_return_is_absent_from_the_window_for_the_named_ticker():
    # TRENT.NS has a real, documented exclusion on 2026-01-01 (see
    # app/data/exclusions.py) -- build a series with a huge move landing
    # exactly on that date and confirm it never reaches stdev/mean.
    dated_prices = [(date(2025, 12, 25) + timedelta(days=i), 100.0 * (1.01 ** i)) for i in range(7)]
    dated_prices.append((date(2026, 1, 1), dated_prices[-1][1] * 0.30))  # the excluded -70% "return"
    dated_prices.append((date(2026, 1, 2), dated_prices[-1][1] * 1.01))
    series = _points_with_dates(dated_prices)

    result = compute_baseline_from_series("TRENT.NS", series)
    assert result is not None
    # A -70% single-day return would dwarf every other ~1% return in the
    # window if it leaked in -- confirm the window stayed calm instead.
    assert result.stdev_return_30d is not None and result.stdev_return_30d < 0.02
    assert result.mean_return_30d is not None and result.mean_return_30d < 0.02


def test_excluded_date_does_not_affect_a_different_ticker_with_the_same_price_pattern():
    # The exact same price pattern, but for a ticker with no exclusion entry
    # -- the huge move must be fully present in its stdev/mean.
    dated_prices = [(date(2025, 12, 25) + timedelta(days=i), 100.0 * (1.01 ** i)) for i in range(7)]
    dated_prices.append((date(2026, 1, 1), dated_prices[-1][1] * 0.30))
    dated_prices.append((date(2026, 1, 2), dated_prices[-1][1] * 1.01))
    series = _points_with_dates(dated_prices)

    result = compute_baseline_from_series("SOME_OTHER_TICKER.NS", series)
    assert result is not None
    # The -70% return is now the dominant contributor to stdev -- unaffected
    # by TRENT.NS's exclusion, since exclusions are keyed by ticker.
    assert result.stdev_return_30d is not None and result.stdev_return_30d > 0.1


def test_excluded_date_price_point_itself_is_untouched_only_the_return_is_dropped():
    # The day AFTER the excluded date must still compute its own return
    # normally (using the excluded date's real stored price as the prior
    # close) -- only the return ATTRIBUTED TO the excluded date disappears,
    # never the underlying price observation itself.
    dated_prices = [
        (date(2025, 12, 30), 100.0),
        (date(2025, 12, 31), 100.0),
        (date(2026, 1, 1), 50.0),  # excluded date's own price: real, untouched
        (date(2026, 1, 2), 55.0),  # +10% from the excluded date's real close
    ]
    series = _points_with_dates(dated_prices)
    result = compute_baseline_from_series("TRENT.NS", series)
    assert result is not None
    # Only 2 returns should survive: 12-31 (0%) and 01-02 (+10%) -- 01-01's
    # return (-50%) is excluded, but 01-02's return still uses 01-01's real
    # price (50.0) as its denominator, proving the price point itself lives on.
    assert result.sample_size == 2
    assert round(result.mean_return_30d, 4) == round((0.0 + 0.10) / 2, 4)


def test_excluded_dates_for_is_keyed_by_ticker():
    assert date(2026, 1, 1) in excluded_dates_for("TRENT.NS")
    assert date(2026, 1, 1) in excluded_dates_for("ITC.NS")
    assert excluded_dates_for("RELIANCE.NS") == set()


def test_excluded_date_extends_window_back_one_extra_day_when_history_allows():
    # Deliberate window-shifting decision (see exclusions.py): with ample
    # prior history, sample_size stays at a full 30 -- the window reaches
    # one extra real trading day further back rather than shrinking to 29.
    dated_prices = [(date(2025, 11, 1) + timedelta(days=i), 100.0 * (1.005 ** i)) for i in range(63)]
    # Overwrite the price on 2026-01-01 to create a huge excluded move
    # without disturbing any other day's price.
    idx = next(i for i, (d, _) in enumerate(dated_prices) if d == date(2026, 1, 1))
    d, _ = dated_prices[idx]
    prev_price = dated_prices[idx - 1][1]
    dated_prices[idx] = (d, prev_price * 0.5)
    series = _points_with_dates(dated_prices)

    result = compute_baseline_from_series("TRENT.NS", series)
    assert result is not None
    assert result.sample_size == 30  # not 29 -- extended back, not shrunk


def test_excluded_date_shrinks_window_when_not_enough_prior_history_to_extend_back():
    # Same exclusion, but now there's only exactly enough history for a
    # 30-sample window WITHOUT any spare day to reach back into -- sample_size
    # must legitimately drop to 29 rather than fabricate a 31st observation.
    dated_prices = [(date(2025, 12, 2) + timedelta(days=i), 100.0 * (1.005 ** i)) for i in range(31)]
    idx = next(i for i, (d, _) in enumerate(dated_prices) if d == date(2026, 1, 1))
    d, _ = dated_prices[idx]
    prev_price = dated_prices[idx - 1][1]
    dated_prices[idx] = (d, prev_price * 0.5)
    series = _points_with_dates(dated_prices)

    result = compute_baseline_from_series("TRENT.NS", series)
    assert result is not None
    assert result.sample_size == 29


def test_every_known_exclusion_has_a_non_empty_reason():
    # Auditability requirement: no exclusion may exist without a documented
    # reason -- this is what makes the constant discoverable, not just a
    # bare (ticker, date) pair.
    assert len(KNOWN_EXCLUSIONS) > 0
    for exclusion in KNOWN_EXCLUSIONS:
        assert isinstance(exclusion, DataExclusion)
        assert exclusion.reason.strip() != ""
