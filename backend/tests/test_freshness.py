from app.services.freshness import classify_freshness


LIVE, RECENT, DELAYED, STALE = 5, 15, 30, 30  # demo-compressed defaults


def test_live_below_first_threshold():
    assert classify_freshness(0, LIVE, RECENT, DELAYED, STALE) == "LIVE"
    assert classify_freshness(4.9, LIVE, RECENT, DELAYED, STALE) == "LIVE"


def test_recent_band():
    assert classify_freshness(5, LIVE, RECENT, DELAYED, STALE) == "RECENT"
    assert classify_freshness(14.9, LIVE, RECENT, DELAYED, STALE) == "RECENT"


def test_delayed_band():
    assert classify_freshness(15, LIVE, RECENT, DELAYED, STALE) == "DELAYED"
    assert classify_freshness(29.9, LIVE, RECENT, DELAYED, STALE) == "DELAYED"


def test_stale_at_and_beyond_threshold():
    assert classify_freshness(30, LIVE, RECENT, DELAYED, STALE) == "STALE"
    assert classify_freshness(9999, LIVE, RECENT, DELAYED, STALE) == "STALE"


def test_wider_delayed_band_when_stale_seconds_exceeds_delayed_seconds():
    # delayed_seconds=400 and stale_seconds=600 are deliberately distinct
    # here, to exercise the "age < stale_seconds -> still DELAYED" branch
    # (a no-op at the demo defaults, where delayed_seconds == stale_seconds).
    assert classify_freshness(200, 15, 120, 400, 600) == "DELAYED"  # < delayed_seconds
    assert classify_freshness(500, 15, 120, 400, 600) == "DELAYED"  # >= delayed_seconds, < stale_seconds
    assert classify_freshness(600, 15, 120, 400, 600) == "STALE"
