"""Workstream 3 — LiveDelayedNSEProvider. Additive, opt-in, never wired into
scoring. Tests cover: the provider's own freshness behavior in isolation (no
new error-handling path — reuses classify_freshness exactly like
FaultInjectingProvider), the /provider/live-status route's LIVE_PROVIDER_ENABLED
gate, and — the most important regression guard — that the flag being off
(the default) changes nothing observable anywhere else in the app.
"""

import types
from datetime import datetime, timezone

import httpx
import pandas as pd
import pytest

from app.config import settings
from app.providers.live_delayed_nse import LiveDelayedNSEProvider

THRESHOLDS = dict(live_seconds=5, recent_seconds=15, delayed_seconds=30, stale_seconds=30)


# --- Unit: the provider in isolation, no HTTP layer, no real network ------


def test_get_status_is_unavailable_before_any_successful_fetch():
    provider = LiveDelayedNSEProvider(**THRESHOLDS)
    status = provider.get_status()
    assert status.state == "UNAVAILABLE"


def test_a_fetch_exception_is_swallowed_per_ticker_and_status_stays_unavailable(monkeypatch):
    provider = LiveDelayedNSEProvider(**THRESHOLDS)

    def raise_error(self, ticker):
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(LiveDelayedNSEProvider, "_fetch_one", raise_error)

    ticks = provider.get_ticks(["RELIANCE.NS"])
    assert ticks == []
    # No new error-handling path: this is the exact same UNAVAILABLE branch
    # as "no fetch has ever succeeded" — not a distinct failure state.
    assert provider.get_status().state == "UNAVAILABLE"
    assert "failed" in provider.last_detail.lower()


def test_a_successful_fetch_tags_the_real_source_and_moves_off_unavailable(monkeypatch):
    provider = LiveDelayedNSEProvider(**THRESHOLDS)

    fake_tick_time = datetime.now(timezone.utc)

    def fake_fetch_one(self, ticker):
        from app.providers.base import Tick

        return Tick(ticker=ticker, price=1234.5, volume=1000, timestamp=fake_tick_time, source="live_delayed_unofficial")

    monkeypatch.setattr(LiveDelayedNSEProvider, "_fetch_one", fake_fetch_one)

    ticks = provider.get_ticks(["RELIANCE.NS"])
    assert len(ticks) == 1
    assert ticks[0].source == "live_delayed_unofficial"
    assert provider.get_status().state == "LIVE"


def test_one_tickers_failure_does_not_abort_the_whole_batch(monkeypatch):
    provider = LiveDelayedNSEProvider(**THRESHOLDS)

    def flaky_fetch_one(self, ticker):
        from app.providers.base import Tick

        if ticker == "BROKEN.NS":
            raise RuntimeError("simulated failure for this ticker only")
        return Tick(ticker=ticker, price=100.0, volume=500, timestamp=datetime.now(timezone.utc), source="live_delayed_unofficial")

    monkeypatch.setattr(LiveDelayedNSEProvider, "_fetch_one", flaky_fetch_one)

    ticks = provider.get_ticks(["RELIANCE.NS", "BROKEN.NS", "INFY.NS"])
    assert {t.ticker for t in ticks} == {"RELIANCE.NS", "INFY.NS"}
    assert provider.get_status().state == "LIVE"  # the batch still counts as a successful fetch overall


def test_empty_dataframe_is_treated_as_no_usable_data_not_an_exception(monkeypatch):
    provider = LiveDelayedNSEProvider(**THRESHOLDS)

    class FakeYfTicker:
        def __init__(self, ticker):
            pass

        def history(self, *args, **kwargs):
            return pd.DataFrame()  # empty — e.g. an unknown/delisted symbol

    fake_yf_module = types.SimpleNamespace(Ticker=FakeYfTicker)
    monkeypatch.setitem(__import__("sys").modules, "yfinance", fake_yf_module)

    ticks = provider.get_ticks(["NOTAREALTICKER.NS"])
    assert ticks == []
    assert provider.get_status().state == "UNAVAILABLE"


# --- Integration: the /provider/live-status route and its gate -----------


async def test_live_status_404s_when_flag_unset(client):
    """Default-off regression guard: with LIVE_PROVIDER_ENABLED unset
    (settings default False, matching the `client` fixture's real startup),
    the route is provably inert — not just unused, actually absent."""
    assert settings.live_provider_enabled is False
    resp = await client.get("/provider/live-status")
    assert resp.status_code == 404


async def test_app_state_live_provider_is_none_when_flag_unset(client):
    # `client` keeps the real app's lifespan open for the duration of this
    # test — confirm the opt-in provider was never even constructed, not
    # just unreachable via the route.
    from app.main import app as fastapi_app

    assert fastapi_app.state.live_provider is None


@pytest.mark.parametrize("with_mocked_fetch", [True])
async def test_live_status_attempts_a_real_fetch_when_enabled(monkeypatch, db_pool, with_mocked_fetch):
    """LIVE_PROVIDER_ENABLED=true: the app starts correctly and a real fetch
    ATTEMPT occurs on every call to /provider/live-status. The underlying
    yfinance call is mocked here (network calls are unreliable in CI/test
    runs — the provider's real-request behavior is exercised directly, live,
    in the manual verification documented in PROGRESS.md/PRODUCT.md) but the
    call path through get_ticks()/get_status() is entirely real."""
    from app.config import settings as live_settings
    from app.main import app as fastapi_app

    fetch_calls: list[str] = []

    def fake_fetch_one(self, ticker):
        from app.providers.base import Tick

        fetch_calls.append(ticker)
        return Tick(ticker=ticker, price=2500.0, volume=42, timestamp=datetime.now(timezone.utc), source="live_delayed_unofficial")

    monkeypatch.setattr("app.providers.live_delayed_nse.LiveDelayedNSEProvider._fetch_one", fake_fetch_one)

    previous_live = live_settings.live_provider_enabled
    previous_scheduler = live_settings.scheduler_enabled
    live_settings.live_provider_enabled = True
    live_settings.scheduler_enabled = False
    try:
        async with fastapi_app.router.lifespan_context(fastapi_app):
            assert fastapi_app.state.live_provider is not None  # app starts correctly with the flag on

            transport = httpx.ASGITransport(app=fastapi_app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/provider/live-status", params={"ticker": "RELIANCE.NS"})
                assert resp.status_code == 200
                body = resp.json()
                assert body["state"] == "LIVE"
                assert body["tick"]["ticker"] == "RELIANCE.NS"
                assert body["tick"]["source"] == "live_delayed_unofficial"
                assert fetch_calls == ["RELIANCE.NS"]  # a real fetch attempt occurred
    finally:
        live_settings.live_provider_enabled = previous_live
        live_settings.scheduler_enabled = previous_scheduler
