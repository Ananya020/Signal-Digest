"""Today's Brief, wired into GET /digest end-to-end — real Postgres, real
FastAPI app. Confirms the `brief` field reflects real current digest state
(not a cached/stale snapshot) as flags are acked down, and that zero active
signals means `brief: null`, never an empty/awkward string.
"""

from datetime import date

from tests.helpers import insert_flag


async def test_brief_is_null_with_zero_active_signals(client, demo_watchlist, test_ticker):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    assert resp.status_code == 200
    assert resp.json()["brief"] is None


async def test_brief_present_for_a_single_active_signal(client, db_pool, demo_watchlist, test_ticker):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await insert_flag(db_pool, test_ticker, date(2026, 3, 1), severity="significant", severity_rank=2, z_score=2.8)

    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    body = resp.json()
    bare = test_ticker.replace(".NS", "")
    assert body["brief"] == f"{bare} is the one signal that stands out today, moving 2.8σ outside its normal range."


async def test_brief_updates_as_flags_are_acked_down_to_one_then_zero(
    client, db_pool, demo_watchlist, test_ticker, test_ticker_2
):
    # conftest.py's test_ticker/test_ticker_2 share sector="Test" — real
    # concentration, not a fabricated example.
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker_2})

    flag_1 = await insert_flag(db_pool, test_ticker, date(2026, 3, 1), severity="extreme", severity_rank=3, z_score=4.1)
    flag_2 = await insert_flag(db_pool, test_ticker_2, date(2026, 3, 1), severity="notable", severity_rank=1, z_score=2.1)

    resp1 = await client.get(f"/watchlists/{demo_watchlist}/digest")
    body1 = resp1.json()
    bare_1 = test_ticker.replace(".NS", "")
    assert body1["brief"] == (
        f"Two unusual moves today, concentrated in Test — {bare_1} is the most statistically unusual, "
        "including one extreme-severity move."
    )

    # Ack the weaker flag — one real signal remains -> single-signal branch.
    await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_2]})
    resp2 = await client.get(f"/watchlists/{demo_watchlist}/digest")
    body2 = resp2.json()
    assert body2["brief"] == f"{bare_1} is the one signal that stands out today, moving 4.1σ outside its normal range."

    # Ack the last remaining flag — zero active signals -> brief disappears.
    await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_1]})
    resp3 = await client.get(f"/watchlists/{demo_watchlist}/digest")
    assert resp3.json()["brief"] is None


async def test_brief_excludes_volatility_regime_flags_same_as_the_digest_itself(
    client, db_pool, demo_watchlist, test_ticker
):
    """The brief is built from the exact rows GET /digest returns — it must
    never see volatility_regime flags the digest itself deliberately hides
    (PRODUCT.md)."""
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await insert_flag(db_pool, test_ticker, date(2026, 3, 1), signal_type="volatility_regime", z_score=None)

    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    body = resp.json()
    assert body["flags"] == []
    assert body["brief"] is None
