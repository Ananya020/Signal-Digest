"""Phase 3 API integration tests — real Postgres, real FastAPI app via ASGI
transport (no mocks). Covers digest/ETag semantics, ack idempotency,
multi-client acknowledgement safety, cross-watchlist isolation at the real
join level, ownership, and evidence.
"""

from datetime import date, datetime, timedelta, timezone

from app.data.baselines import compute_and_store_baseline, load_latest_baseline
from app.services.scoring import compute_return
from tests.helpers import insert_flag


async def test_digest_etag_full_sequence(client, db_pool, demo_watchlist, test_ticker):
    add_resp = await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    assert add_resp.status_code == 200

    flag_id = await insert_flag(db_pool, test_ticker, date(2026, 1, 1), severity_rank=1)

    resp1 = await client.get(f"/watchlists/{demo_watchlist}/digest")
    assert resp1.status_code == 200
    etag1 = resp1.headers["etag"]
    assert len(resp1.json()["flags"]) == 1

    resp2 = await client.get(f"/watchlists/{demo_watchlist}/digest", headers={"If-None-Match": etag1})
    assert resp2.status_code == 304
    assert resp2.headers["etag"] == etag1
    assert resp2.content == b""

    ack_resp = await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_id]})
    assert ack_resp.status_code == 200
    assert ack_resp.json()["acked"] == [flag_id]

    # Old ETag is now stale -> must return 200 with fresh content + a new ETag
    resp3 = await client.get(f"/watchlists/{demo_watchlist}/digest", headers={"If-None-Match": etag1})
    assert resp3.status_code == 200
    etag2 = resp3.headers["etag"]
    assert etag2 != etag1
    assert resp3.json()["flags"] == []

    # New ETag matches current state -> 304
    resp4 = await client.get(f"/watchlists/{demo_watchlist}/digest", headers={"If-None-Match": etag2})
    assert resp4.status_code == 304
    assert resp4.headers["etag"] == etag2


async def test_ack_is_idempotent(client, db_pool, demo_watchlist, test_ticker):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    flag_id = await insert_flag(db_pool, test_ticker, date(2026, 1, 2), severity_rank=1)

    resp_a = await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_id]})
    hash_a = resp_a.json()["hash"]
    resp_b = await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_id]})
    hash_b = resp_b.json()["hash"]

    assert hash_a == hash_b  # hash stable across the repeated ack

    count = await db_pool.fetchval(
        "SELECT count(*) FROM flag_ack WHERE flag_id = $1 AND watchlist_id = $2", flag_id, demo_watchlist
    )
    assert count == 1  # no duplicate row


async def test_multiclient_sequential_acks_both_survive_forward_order(
    client, db_pool, demo_watchlist, test_ticker, test_ticker_2
):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker_2})
    flag_x = await insert_flag(db_pool, test_ticker, date(2026, 1, 3), severity_rank=1)
    flag_y = await insert_flag(db_pool, test_ticker_2, date(2026, 1, 3), severity_rank=1)

    # Client A fetches a view, then acks X.
    await client.get(f"/watchlists/{demo_watchlist}/digest")
    resp_a = await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_x]})
    assert resp_a.status_code == 200

    # Client B, using its own (now stale relative to A's change) view, acks Y.
    await client.get(f"/watchlists/{demo_watchlist}/digest")
    resp_b = await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_y]})
    assert resp_b.status_code == 200

    rows = await db_pool.fetch("SELECT flag_id FROM flag_ack WHERE watchlist_id = $1", demo_watchlist)
    acked_ids = {r["flag_id"] for r in rows}
    assert acked_ids == {flag_x, flag_y}  # neither ack overwrote the other

    final = await client.get(f"/watchlists/{demo_watchlist}/digest")
    assert final.json()["flags"] == []


async def test_multiclient_sequential_acks_both_survive_reverse_order(
    client, db_pool, demo_watchlist, test_ticker, test_ticker_2
):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker_2})
    flag_x = await insert_flag(db_pool, test_ticker, date(2026, 1, 4), severity_rank=1)
    flag_y = await insert_flag(db_pool, test_ticker_2, date(2026, 1, 4), severity_rank=1)

    # Reverse order: B (Y) acks before A (X).
    await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_y]})
    await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_x]})

    rows = await db_pool.fetch("SELECT flag_id FROM flag_ack WHERE watchlist_id = $1", demo_watchlist)
    acked_ids = {r["flag_id"] for r in rows}
    assert acked_ids == {flag_x, flag_y}


async def test_cross_watchlist_isolation_at_real_join(
    client, db_pool, demo_watchlist, demo_watchlist_2, test_ticker, test_ticker_2
):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await client.post(f"/watchlists/{demo_watchlist_2}/items", json={"ticker": test_ticker_2})

    flag_1 = await insert_flag(db_pool, test_ticker, date(2026, 1, 5), severity_rank=1)
    flag_2 = await insert_flag(db_pool, test_ticker_2, date(2026, 1, 5), severity_rank=1)

    digest_1 = await client.get(f"/watchlists/{demo_watchlist}/digest")
    digest_2 = await client.get(f"/watchlists/{demo_watchlist_2}/digest")

    assert [f["id"] for f in digest_1.json()["flags"]] == [flag_1]
    assert [f["id"] for f in digest_2.json()["flags"]] == [flag_2]
    hash_2_before = digest_2.headers["etag"]

    # Acking watchlist 1's flag must not affect watchlist 2's digest/hash at all.
    await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_1]})

    digest_2_after = await client.get(f"/watchlists/{demo_watchlist_2}/digest")
    assert digest_2_after.headers["etag"] == hash_2_before
    assert [f["id"] for f in digest_2_after.json()["flags"]] == [flag_2]


async def test_ownership_demo_user_can_access_own_watchlist(client, demo_watchlist):
    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    assert resp.status_code == 200


async def test_ownership_rejects_non_owned_watchlist(client, foreign_watchlist):
    digest_resp = await client.get(f"/watchlists/{foreign_watchlist}/digest")
    assert digest_resp.status_code == 404

    ack_resp = await client.post(f"/watchlists/{foreign_watchlist}/ack", json={"flag_ids": []})
    assert ack_resp.status_code == 404

    items_resp = await client.post(f"/watchlists/{foreign_watchlist}/items", json={"ticker": "RELIANCE.NS"})
    assert items_resp.status_code == 404


async def _seed_price_series(db_pool, ticker, base_ts, prices):
    for i, price in enumerate(prices):
        await db_pool.execute(
            "INSERT INTO price_ticks (ticker, price, volume, ts, source) VALUES ($1, $2, $3, $4, 'real_historical') "
            "ON CONFLICT DO NOTHING",
            ticker, price, 1000, base_ts + timedelta(days=i),
        )


async def test_evidence_from_real_price_ticks_and_persisted_flag(client, db_pool, test_ticker):
    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    prices = [100.0 + i for i in range(35)]
    await _seed_price_series(db_pool, test_ticker, base_ts, prices)
    await compute_and_store_baseline(db_pool, test_ticker)
    baseline = await load_latest_baseline(db_pool, test_ticker)

    trading_day = (base_ts + timedelta(days=34)).date()
    flagged_return = compute_return(prices[33], prices[34])
    z = (flagged_return - baseline.mean_return_30d) / baseline.stdev_return_30d
    flag_id = await insert_flag(db_pool, test_ticker, trading_day, severity_rank=2, z_score=z)

    resp = await client.get(f"/tickers/{test_ticker}/evidence", params={"flag_id": flag_id})
    assert resp.status_code == 200
    body = resp.json()

    assert body["ticker"] == test_ticker
    assert len(body["points"]) == 30  # capped at WINDOW_SIZE
    assert body["flagged_point"]["date"] == trading_day.isoformat()
    # All returns in this monotonically-increasing-by-$1 series are positive.
    assert all(p["return"] > 0 for p in body["points"])
    # mean_return/stdev_return come from the SAME baseline row the flag's
    # z_score was computed from — not independently recomputed.
    assert body["mean_return"] == baseline.mean_return_30d
    assert body["stdev_return"] == baseline.stdev_return_30d


async def test_flagged_point_zscore_is_reproducible_from_response(client, db_pool, test_ticker):
    """The core correctness property of this screen: the displayed chart
    (mean_return, stdev_return, points) and the displayed z_score must be
    algebraically consistent — this is the one screen whose entire purpose
    is proving the system isn't a black box."""
    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    prices = [100.0 + i + (i % 3) * 0.7 for i in range(40)]  # non-trivial, still real, series
    await _seed_price_series(db_pool, test_ticker, base_ts, prices)
    await compute_and_store_baseline(db_pool, test_ticker)
    baseline = await load_latest_baseline(db_pool, test_ticker)

    # Flag an EARLIER day than the baseline's own window (day index 10),
    # mirroring the real static-baseline situation from the replay run —
    # the flagged day need not fall inside the plotted points window.
    trading_day = (base_ts + timedelta(days=10)).date()
    flagged_return = compute_return(prices[9], prices[10])
    z = (flagged_return - baseline.mean_return_30d) / baseline.stdev_return_30d
    flag_id = await insert_flag(db_pool, test_ticker, trading_day, severity_rank=1, z_score=z)

    resp = await client.get(f"/tickers/{test_ticker}/evidence", params={"flag_id": flag_id})
    assert resp.status_code == 200
    body = resp.json()

    recomputed_z = (body["flagged_point"]["return"] - body["mean_return"]) / body["stdev_return"]
    # NUMERIC(6,3) column rounds the stored z_score to 3 decimals — tolerance
    # accounts for that quantization, not for any algorithmic drift.
    assert abs(recomputed_z - body["flagged_point"]["z_score"]) < 5e-3


async def test_evidence_rejects_ticker_flag_mismatch(client, db_pool, test_ticker, test_ticker_2):
    flag_id = await insert_flag(db_pool, test_ticker, date(2026, 1, 6), severity_rank=1)
    resp = await client.get(f"/tickers/{test_ticker_2}/evidence", params={"flag_id": flag_id})
    assert resp.status_code == 400


async def test_evidence_unknown_flag_returns_404(client, test_ticker):
    resp = await client.get(f"/tickers/{test_ticker}/evidence", params={"flag_id": 99999999})
    assert resp.status_code == 404


async def test_evidence_unknown_ticker_returns_404(client):
    resp = await client.get("/tickers/NOTAREALTICKER.NS/evidence", params={"flag_id": 1})
    assert resp.status_code == 404


async def test_create_watchlist_associates_demo_user(client, db_pool):
    resp = await client.post("/watchlists", json={"name": "My Watchlist"})
    assert resp.status_code == 201
    body = resp.json()
    watchlist_id = body["id"]

    row = await db_pool.fetchrow("SELECT user_id, name FROM watchlists WHERE id = $1", watchlist_id)
    assert row is not None
    assert str(row["user_id"]) == body["user_id"]
    assert row["name"] == "My Watchlist"

    await db_pool.execute("DELETE FROM watchlists WHERE id = $1", watchlist_id)


async def test_add_item_rejects_unknown_ticker(client, demo_watchlist):
    resp = await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": "NOTAREALTICKER.NS"})
    assert resp.status_code == 422


async def test_ack_reports_ignored_flag_with_id_and_reason(client, db_pool, demo_watchlist, test_ticker):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    valid_flag_id = await insert_flag(db_pool, test_ticker, date(2026, 1, 7), severity_rank=1)
    nonexistent_flag_id = 999999999

    resp = await client.post(
        f"/watchlists/{demo_watchlist}/ack",
        json={"flag_ids": [valid_flag_id, nonexistent_flag_id]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["acked"] == [valid_flag_id]
    assert body["ignored"] == [{"id": nonexistent_flag_id, "reason": "flag_not_found"}]


async def test_add_item_is_idempotent_upsert(client, demo_watchlist, test_ticker):
    resp1 = await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    resp2 = await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
