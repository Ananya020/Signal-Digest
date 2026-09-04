"""RELIABILITY.md #10 — timezone handling. `trading_day` bucketing must be
computed in Asia/Kolkata, never server-local or UTC-naive — a wrong-day
bucketing silently breaks the UNIQUE(ticker, trading_day, signal_type)
constraint's semantics.

Tests a tick timestamp near a day boundary where the UTC calendar date and
the IST calendar date actually differ: 2026-01-15 19:30 UTC is already
2026-01-16 01:00 IST (UTC+5:30) — a case where naively taking `.date()` on
a UTC-aware datetime gives the wrong trading day.
"""

from datetime import date, datetime, timezone

from app.providers.base import Tick
from app.services.scoring import trading_day_from_tick


def test_trading_day_uses_ist_date_not_utc_date_near_midnight_boundary():
    # 19:30 UTC on Jan 15 = 01:00 IST on Jan 16 (UTC+5:30 crosses midnight).
    utc_tick_time = datetime(2026, 1, 15, 19, 30, tzinfo=timezone.utc)
    tick = Tick(ticker="X.NS", price=100.0, volume=1000, timestamp=utc_tick_time, source="replay_simulated")

    trading_day = trading_day_from_tick(tick)

    assert trading_day == date(2026, 1, 16)  # correct IST day
    assert trading_day != utc_tick_time.date()  # would be Jan 15 if computed naively in UTC


def test_trading_day_matches_utc_date_when_well_inside_the_ist_day():
    # 10:00 UTC = 15:30 IST — same calendar date either way. Real ingestion
    # (seed_historical_data.py) anchors closes at 15:30 IST, which is why
    # this specific bug was previously masked in production data.
    utc_tick_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    tick = Tick(ticker="X.NS", price=100.0, volume=1000, timestamp=utc_tick_time, source="replay_simulated")

    assert trading_day_from_tick(tick) == date(2026, 1, 15)
