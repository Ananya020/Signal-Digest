import time
from datetime import datetime, timedelta, timezone

import pytest

from app.providers.fault_injecting import FaultInjectingProvider, ProviderUnavailableError
from app.providers.historical_replay import HistoricalReplayProvider, PricePoint, ReplayClock
from app.services.provider_state import load_provider_state, save_provider_state


def make_history(ticker: str, prices: list[float]) -> dict:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        ticker: [
            PricePoint(ts=start + timedelta(days=i), price=p, volume=1000)
            for i, p in enumerate(prices)
        ]
    }


def make_provider(prices=(100.0, 105.0, 110.0), **threshold_overrides):
    history = make_history("X.NS", list(prices))
    wrapped = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=1))
    thresholds = dict(live_seconds=5, recent_seconds=15, delayed_seconds=30, stale_seconds=30)
    thresholds.update(threshold_overrides)
    return FaultInjectingProvider(wrapped=wrapped, **thresholds)


def test_outage_raises_on_get_ticks_and_reports_unavailable():
    provider = make_provider()
    provider.set_mode("outage")

    with pytest.raises(ProviderUnavailableError):
        provider.get_ticks(["X.NS"])

    status = provider.get_status()
    assert status.state == "UNAVAILABLE"


def test_outage_does_not_touch_wrapped_provider_state():
    provider = make_provider()
    step_before = provider.wrapped.clock.current()
    provider.set_mode("outage")

    with pytest.raises(ProviderUnavailableError):
        provider.get_ticks(["X.NS"])
    provider.advance()  # no-op while outage

    assert provider.wrapped.clock.current() == step_before  # untouched underneath


def test_stale_freezes_replay_position_across_repeated_calls():
    provider = make_provider()
    provider.set_mode("stale")

    tick1 = provider.get_ticks(["X.NS"])[0]
    provider.advance()  # no-op, frozen
    tick2 = provider.get_ticks(["X.NS"])[0]
    provider.advance()
    tick3 = provider.get_ticks(["X.NS"])[0]

    assert tick1.price == tick2.price == tick3.price  # same frozen tick every time


def test_stale_does_not_refresh_last_successful_fetch():
    provider = make_provider()
    original_fetch_time = provider.last_successful_fetch
    provider.set_mode("stale")

    provider.get_ticks(["X.NS"])
    provider.advance()
    provider.get_ticks(["X.NS"])

    assert provider.last_successful_fetch == original_fetch_time


def test_age_seconds_crosses_thresholds_via_real_elapsed_time():
    # Real sleep, tiny thresholds, to prove age_seconds is genuine wall-clock
    # time — not fast-forwarded or faked.
    provider = make_provider(live_seconds=0.05, recent_seconds=0.15, delayed_seconds=0.3, stale_seconds=0.3)
    provider.set_mode("stale")

    assert provider.get_status().state == "LIVE"
    time.sleep(0.08)
    assert provider.get_status().state == "RECENT"
    time.sleep(0.15)
    assert provider.get_status().state == "DELAYED"
    time.sleep(0.2)
    assert provider.get_status().state == "STALE"


def test_normal_mode_refreshes_last_successful_fetch_on_get_ticks():
    provider = make_provider()
    provider.last_successful_fetch = datetime.now(timezone.utc) - timedelta(seconds=100)
    provider.get_ticks(["X.NS"])
    age = (datetime.now(timezone.utc) - provider.last_successful_fetch).total_seconds()
    assert age < 1  # freshly refreshed


def test_recover_transitions_to_normal_and_does_not_snap_freshness():
    provider = make_provider()
    provider.last_successful_fetch = datetime.now(timezone.utc) - timedelta(seconds=100)
    provider.set_mode("stale")
    assert provider.get_status().state == "STALE"

    provider.set_mode("normal")  # what /admin/fault does for {"mode": "recover"}
    # Freshness does NOT snap back until the next successful get_ticks().
    assert provider.get_status().state == "STALE"

    provider.get_ticks(["X.NS"])  # the "next scheduler tick" firing naturally
    assert provider.get_status().state == "LIVE"


def test_recover_resumes_replay_position_from_where_it_was_left_not_recalculated():
    provider = make_provider(prices=(100.0, 105.0, 110.0, 115.0))
    provider.set_mode("stale")
    provider.get_ticks(["X.NS"])
    provider.advance()  # no-op, still frozen
    provider.advance()  # no-op again

    provider.set_mode("normal")
    tick = provider.get_ticks(["X.NS"])[0]
    assert tick.price == 105.0  # step 1's value — resumed from where it was left
    provider.advance()
    tick2 = provider.get_ticks(["X.NS"])[0]
    assert tick2.price == 110.0  # advances normally from there, not recalculated


async def test_provider_state_persists_mode_across_simulated_restart(db_pool):
    await save_provider_state(db_pool, "stale", datetime.now(timezone.utc), datetime.now(timezone.utc))

    # Simulate a fresh process: brand-new provider instance, default mode.
    fresh_provider = make_provider()
    assert fresh_provider.mode == "normal"  # in-memory default before hydration

    await fresh_provider.sync_from_db(db_pool)
    assert fresh_provider.mode == "stale"  # read from DB, not the in-memory default

    # cleanup
    await save_provider_state(db_pool, "normal", None, None)


async def test_provider_state_row_reflects_last_write(db_pool):
    await save_provider_state(db_pool, "outage", datetime.now(timezone.utc), datetime.now(timezone.utc))
    await save_provider_state(db_pool, "stale", datetime.now(timezone.utc), datetime.now(timezone.utc))  # last-write-wins

    row = await load_provider_state(db_pool)
    assert row["mode"] == "stale"

    await save_provider_state(db_pool, "normal", None, None)


async def test_restart_during_stale_correctly_preserves_staleness_not_reset_to_live(db_pool):
    """Regression test for a real bug found during Phase 4 review: freshness
    classification depends entirely on `age = now - last_successful_fetch`
    (frozen_at is cosmetic, only used in `detail`). Before this fix,
    last_successful_fetch was not persisted, so a restart during a genuine
    'stale' fault reset the age clock to the restart moment and
    get_status() incorrectly reported LIVE despite the feed having been
    stale for real minutes beforehand."""
    long_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    provider1 = make_provider()
    provider1.mode = "stale"
    provider1.frozen_at = long_ago
    provider1.last_successful_fetch = long_ago
    await provider1.persist(db_pool)

    assert provider1.get_status().state == "STALE"

    # Simulate a full process restart: brand-new instance, in-memory defaults.
    provider2 = make_provider()
    await provider2.sync_from_db(db_pool)

    status = provider2.get_status()
    assert status.state == "STALE"  # NOT "LIVE" — the bug this test catches
    assert status.age_seconds > 290  # real elapsed time survived the restart

    await save_provider_state(db_pool, "normal", None, None)


async def test_restart_during_outage_remains_unavailable(db_pool):
    """outage was always safe across a restart (its UNAVAILABLE branch never
    consults age_seconds) — confirmed explicitly so this isn't just assumed
    by symmetry with the stale fix above."""
    long_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    provider1 = make_provider()
    provider1.mode = "outage"
    provider1.frozen_at = long_ago
    await provider1.persist(db_pool)

    provider2 = make_provider()
    await provider2.sync_from_db(db_pool)

    assert provider2.get_status().state == "UNAVAILABLE"

    await save_provider_state(db_pool, "normal", None, None)
