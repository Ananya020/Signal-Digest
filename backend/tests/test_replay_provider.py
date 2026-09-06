from datetime import datetime, timedelta, timezone

from app.providers.historical_replay import HistoricalReplayProvider, PricePoint, ReplayClock


def make_history(ticker: str, prices: list[float]) -> dict[str, list[PricePoint]]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        ticker: [
            PricePoint(ts=start + timedelta(days=i), price=p, volume=1000 + i)
            for i, p in enumerate(prices)
        ]
    }


def test_replay_emits_chronological_order():
    history = make_history("X.NS", [100.0, 105.0, 110.0])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock())

    seen_prices = []
    for _ in range(3):
        ticks = provider.get_ticks(["X.NS"])
        seen_prices.append(ticks[0].price)
        provider.advance()

    assert seen_prices == [100.0, 105.0, 110.0]


def test_replay_ticks_tagged_replay_simulated():
    history = make_history("X.NS", [100.0])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock())
    ticks = provider.get_ticks(["X.NS"])
    assert ticks[0].source == "replay_simulated"


def test_replay_uses_real_historical_values_not_random():
    history = make_history("X.NS", [123.45])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock())
    tick = provider.get_ticks(["X.NS"])[0]
    assert tick.price == 123.45  # exact value from history, no jitter applied


def test_replay_is_deterministic_given_same_start_position():
    history = make_history("X.NS", [100.0, 105.0, 110.0])

    provider_a = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=1))
    provider_b = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=1))

    assert provider_a.get_ticks(["X.NS"]) == provider_b.get_ticks(["X.NS"])


def test_replay_exhausted_returns_no_ticks_and_unavailable_status():
    history = make_history("X.NS", [100.0])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock())
    provider.advance()  # step 1, but only 1 observation (index 0) exists

    assert provider.get_ticks(["X.NS"]) == []
    assert provider.get_status().state == "UNAVAILABLE"


def test_replay_clock_reset_resumes_from_persisted_step():
    """ReplayClock.reset() is what restart-resumption relies on (see
    FaultInjectingProvider.sync_from_db) — confirm it actually repositions
    current()/get_ticks(), not just the raw counter."""
    history = make_history("X.NS", [100.0, 105.0, 110.0])
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock())

    clock = provider.clock
    clock.advance()
    clock.advance()
    assert clock.current() == 2

    # Simulate a fresh process reading a persisted step back in.
    fresh_clock = ReplayClock()
    fresh_clock.reset(2)
    fresh_provider = HistoricalReplayProvider(history=history, clock=fresh_clock)

    assert fresh_provider.get_ticks(["X.NS"])[0].price == 110.0


def test_multiple_tickers_advance_in_lockstep():
    history = {
        **make_history("A.NS", [1.0, 2.0]),
        **make_history("B.NS", [10.0, 20.0]),
    }
    provider = HistoricalReplayProvider(history=history, clock=ReplayClock())

    ticks = provider.get_ticks(["A.NS", "B.NS"])
    prices = {t.ticker: t.price for t in ticks}
    assert prices == {"A.NS": 1.0, "B.NS": 10.0}

    provider.advance()
    ticks = provider.get_ticks(["A.NS", "B.NS"])
    prices = {t.ticker: t.price for t in ticks}
    assert prices == {"A.NS": 2.0, "B.NS": 20.0}
