"""Workstream 4B — GET /tickers/{ticker}/flags: the historical audit-trail
read used by the frontend's History panel. Distinct from GET /digest (current,
unacked, watchlist-scoped) — this returns every recorded flag for a ticker,
reverse chronological, regardless of watchlist membership or ack state.
"""

from datetime import date

from tests.helpers import insert_flag


async def test_returns_flags_reverse_chronological(client, db_pool, test_ticker):
    await insert_flag(db_pool, test_ticker, date(2026, 1, 1), severity="notable", severity_rank=1, z_score=2.1)
    await insert_flag(db_pool, test_ticker, date(2026, 1, 5), severity="extreme", severity_rank=3, z_score=-4.2)
    await insert_flag(db_pool, test_ticker, date(2026, 1, 3), severity="significant", severity_rank=2, z_score=2.8)

    resp = await client.get(f"/tickers/{test_ticker}/flags")
    assert resp.status_code == 200
    body = resp.json()

    assert [row["trading_day"] for row in body] == ["2026-01-05", "2026-01-03", "2026-01-01"]
    assert body[0]["severity"] == "extreme"
    assert body[0]["z_score"] == -4.2
    assert body[0]["signal_type"] == "price_zscore"


async def test_only_the_required_fields_are_exposed(client, db_pool, test_ticker):
    await insert_flag(db_pool, test_ticker, date(2026, 1, 1))
    resp = await client.get(f"/tickers/{test_ticker}/flags")
    row = resp.json()[0]
    assert set(row.keys()) == {"trading_day", "signal_type", "z_score", "severity"}


async def test_empty_for_a_ticker_with_no_recorded_flags(client, test_ticker):
    resp = await client.get(f"/tickers/{test_ticker}/flags")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_unknown_ticker_returns_404(client):
    resp = await client.get("/tickers/NOTAREALTICKER.NS/flags")
    assert resp.status_code == 404


async def test_does_not_leak_other_tickers_flags(client, db_pool, test_ticker, test_ticker_2):
    await insert_flag(db_pool, test_ticker, date(2026, 1, 1))
    await insert_flag(db_pool, test_ticker_2, date(2026, 1, 2))

    resp = await client.get(f"/tickers/{test_ticker}/flags")
    body = resp.json()
    assert len(body) == 1
    assert body[0]["trading_day"] == "2026-01-01"


async def test_current_digest_state_does_not_affect_history_a_ticker_can_have_history_with_no_active_flag(
    client, db_pool, test_ticker, test_watchlist
):
    """A ticker's history must show past flags even when nothing is
    currently unacknowledged for it (e.g. everything's been acked, or it's
    simply not in any watchlist) — history is not derived from the digest."""
    flag_id = await insert_flag(db_pool, test_ticker, date(2026, 1, 1))
    await db_pool.execute(
        "INSERT INTO flag_ack (flag_id, watchlist_id, acked_at) VALUES ($1, $2, now())",
        flag_id, test_watchlist,
    )

    resp = await client.get(f"/tickers/{test_ticker}/flags")
    body = resp.json()
    assert len(body) == 1  # still present in history despite being fully acked
