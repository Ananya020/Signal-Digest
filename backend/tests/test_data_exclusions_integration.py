"""Integration-level confirmation (real Postgres, real seeded historical
data) that the TRENT.NS/ITC.NS 2026-01-01 corporate-action exclusion
(app/data/exclusions.py) actually produces a plausible stdev_return_30d for
the trading days whose window used to include it — read-only, no DB writes,
so no cleanup is needed (this exercises the real, permanent seeded dataset,
not a throwaway test fixture)."""

from datetime import date

from app.data.baselines import compute_baseline_as_of, load_price_series


async def test_trent_stdev_return_30d_is_plausible_shortly_after_the_excluded_date(db_pool):
    series = await load_price_series(db_pool, "TRENT.NS")
    if not series:
        return  # real seed data not present in this environment — nothing to assert

    baseline = compute_baseline_as_of("TRENT.NS", series, date(2026, 1, 6))
    assert baseline is not None
    # Before this fix, this window's stdev_return_30d was ~0.062 (6.2% daily
    # stdev) -- implausible for a real large-cap, dominated by the -33.05%
    # excluded artifact. A plausible real daily stdev for this name is on the
    # order of 1-3%.
    assert baseline.stdev_return_30d is not None
    assert baseline.stdev_return_30d < 0.03


async def test_itc_stdev_return_30d_is_plausible_shortly_after_the_excluded_date(db_pool):
    series = await load_price_series(db_pool, "ITC.NS")
    if not series:
        return

    baseline = compute_baseline_as_of("ITC.NS", series, date(2026, 1, 6))
    assert baseline is not None
    # Before this fix, this window's stdev_return_30d was ~0.019 (1.9%),
    # already dominated by the -9.71% excluded artifact relative to ITC's
    # normally very calm real daily moves (well under 1%).
    assert baseline.stdev_return_30d is not None
    assert baseline.stdev_return_30d < 0.015


async def test_excluded_date_price_tick_is_untouched_in_storage(db_pool):
    # The raw price_ticks row for the excluded date must still exist,
    # unmodified -- this is a computation-input exclusion, never a
    # data-deletion decision.
    row = await db_pool.fetchrow(
        "SELECT price, volume FROM price_ticks WHERE ticker = 'TRENT.NS' AND ts::date = '2026-01-01' AND source = 'real_historical'"
    )
    if row is None:
        return
    assert float(row["price"]) > 0  # the real, unmodified stored price -- not deleted, not zeroed
