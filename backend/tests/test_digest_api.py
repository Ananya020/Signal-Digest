"""Phase 3 API integration tests — real Postgres, real FastAPI app via ASGI
transport (no mocks). Covers digest/ETag semantics, ack idempotency,
multi-client acknowledgement safety, cross-watchlist isolation at the real
join level, ownership, and evidence.
"""

from datetime import date, datetime, timedelta, timezone

from app.data.baselines import compute_baseline_as_of, load_price_series, upsert_baseline
from app.services.scoring import compute_return
from tests.helpers import insert_flag


async def test_digest_excludes_volatility_regime_flags(client, db_pool, demo_watchlist, test_ticker):
    """Deliberate product decision (PRODUCT.md), not a bug: volatility_regime
    is still computed and persisted, just not surfaced in the digest."""
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    price_flag_id = await insert_flag(db_pool, test_ticker, date(2026, 2, 1), signal_type="price_zscore")
    vol_flag_id = await insert_flag(db_pool, test_ticker, date(2026, 2, 1), signal_type="volatility_regime")

    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    ids = [f["id"] for f in resp.json()["flags"]]

    assert price_flag_id in ids
    assert vol_flag_id not in ids
    # Not deleted — still a real row in the table.
    row = await db_pool.fetchrow("SELECT id FROM flags WHERE id = $1", vol_flag_id)
    assert row is not None


async def test_digest_orders_by_absolute_z_score_descending(client, db_pool, demo_watchlist, test_ticker, test_ticker_2):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker_2})

    high_id = await insert_flag(db_pool, test_ticker_2, date(2026, 2, 2), z_score=-4.5)
    mid_id = await insert_flag(db_pool, test_ticker, date(2026, 2, 3), z_score=3.2)

    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    ids = [f["id"] for f in resp.json()["flags"]]

    assert ids == [high_id, mid_id]  # |−4.5| > |3.2|


async def test_digest_surfaces_only_the_most_severe_unacked_flag_per_ticker(
    client, db_pool, demo_watchlist, test_ticker, test_ticker_2
):
    """Verified against real HDFCBANK data: a ticker can legitimately
    accumulate many distinct-trading-day unacknowledged flags over time —
    not a duplicate/timezone bug. The digest's job is "what needs your
    attention right now", so only the single most-severe unacked flag per
    ticker should occupy a digest slot; the rest remain real, unacked, and
    reachable via GET /tickers/{ticker}/flags."""
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker_2})

    older_weaker = await insert_flag(db_pool, test_ticker, date(2026, 1, 1), severity_rank=1, z_score=2.1)
    newer_stronger = await insert_flag(db_pool, test_ticker, date(2026, 1, 15), severity_rank=3, z_score=-4.2)
    other_ticker_flag = await insert_flag(db_pool, test_ticker_2, date(2026, 1, 10), severity_rank=1, z_score=2.3)

    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    ids = [f["id"] for f in resp.json()["flags"]]

    assert ids == [newer_stronger, other_ticker_flag]
    assert older_weaker not in ids

    # The suppressed flag is untouched in the DB — not deleted, not acked.
    row = await db_pool.fetchrow(
        "SELECT 1 FROM flags f LEFT JOIN flag_ack fa ON fa.flag_id = f.id WHERE f.id = $1 AND fa.flag_id IS NULL",
        older_weaker,
    )
    assert row is not None

    # And it's still visible through the real per-ticker history endpoint
    # (that endpoint exposes trading_day/signal_type/z_score/severity, not
    # id — see test_ticker_flags_api.py).
    history_resp = await client.get(f"/tickers/{test_ticker}/flags")
    history_days = {row["trading_day"] for row in history_resp.json()}
    assert {"2026-01-01", "2026-01-15"} <= history_days


async def test_escalation_ack_bust_still_works_on_the_flag_the_digest_surfaces(
    client, db_pool, demo_watchlist, test_ticker
):
    """The suppression above must not interfere with the severity-escalation
    ack-bust rule (flags.py) for whichever flag the digest actually shows —
    that rule operates per flag row keyed by (ticker, trading_day,
    signal_type), independent of digest visibility."""
    from app.services.flags import upsert_flag_with_ack_bust
    from app.services.scoring import FlagCandidate

    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})

    # An older, weaker, already-shown-and-acked flag stays in the background.
    background_id = await insert_flag(db_pool, test_ticker, date(2026, 1, 1), severity_rank=1, z_score=2.1)
    await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [background_id]})

    trading_day = date(2026, 1, 20)
    async with db_pool.acquire() as conn:
        result = await upsert_flag_with_ack_bust(
            conn,
            FlagCandidate(
                ticker=test_ticker, trading_day=trading_day, signal_type="price_zscore",
                z_score=2.2, severity="notable", severity_rank=1, volume_ratio=None,
                sector_relative=None, computed_at=datetime.now(timezone.utc),
                provider_state_at_computation="live",
            ),
        )
    shown_id = result.id

    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    assert [f["id"] for f in resp.json()["flags"]] == [shown_id]

    await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [shown_id]})
    resp_after_ack = await client.get(f"/watchlists/{demo_watchlist}/digest")
    assert resp_after_ack.json()["flags"] == []

    # Escalate the same flag (same ticker/trading_day/signal_type) — must bust its ack.
    async with db_pool.acquire() as conn:
        escalated = await upsert_flag_with_ack_bust(
            conn,
            FlagCandidate(
                ticker=test_ticker, trading_day=trading_day, signal_type="price_zscore",
                z_score=-4.0, severity="extreme", severity_rank=3, volume_ratio=None,
                sector_relative=None, computed_at=datetime.now(timezone.utc),
                provider_state_at_computation="live",
            ),
        )
    assert escalated.id == shown_id
    assert escalated.ack_busted is True

    resp_final = await client.get(f"/watchlists/{demo_watchlist}/digest")
    flags_final = resp_final.json()["flags"]
    assert [f["id"] for f in flags_final] == [shown_id]

    # Step A: the resurfaced flag shows the pre-escalation snapshot, not
    # the new post-escalation values.
    since_last_ack = flags_final[0]["since_last_ack"]
    assert since_last_ack is not None
    assert since_last_ack["severity_rank_at_ack"] == 1
    assert since_last_ack["z_score_at_ack"] == 2.2


async def test_since_last_ack_is_null_for_a_flag_with_no_ack_history(client, db_pool, demo_watchlist, test_ticker):
    """A flag that has never been acked has no baseline to compare
    against — since_last_ack must be null, never fabricated."""
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await insert_flag(db_pool, test_ticker, date(2026, 1, 1), severity_rank=1, z_score=2.1)

    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    flags = resp.json()["flags"]
    assert len(flags) == 1
    assert flags[0]["since_last_ack"] is None


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


async def test_stale_if_none_match_after_multiple_state_changes_returns_full_200(
    client, db_pool, demo_watchlist, test_ticker
):
    """RELIABILITY.md #12 — a client returning after several server-state
    changes (acked flags, new flags) presents a long-stale ETag. The server
    always recomputes the hash server-side, so this should just fall out of
    existing comparison logic — verified explicitly rather than assumed."""
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})

    first = await client.get(f"/watchlists/{demo_watchlist}/digest")
    ancient_etag = first.headers["etag"]  # "several server-state-changes ago"

    # Several state changes happen after the client last saw this etag.
    for day in range(2, 6):
        flag_id = await insert_flag(db_pool, test_ticker, date(2026, 1, day), severity_rank=1)
        await client.post(f"/watchlists/{demo_watchlist}/ack", json={"flag_ids": [flag_id]})
    await insert_flag(db_pool, test_ticker, date(2026, 1, 10), severity_rank=2)

    resp = await client.get(f"/watchlists/{demo_watchlist}/digest", headers={"If-None-Match": ancient_etag})

    assert resp.status_code == 200  # not a false 304
    assert resp.headers["etag"] != ancient_etag
    assert len(resp.json()["flags"]) == 1  # the one still-unacked flag, current data


async def test_garbage_if_none_match_returns_full_200_not_an_error(client, demo_watchlist, test_ticker):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    resp = await client.get(
        f"/watchlists/{demo_watchlist}/digest", headers={"If-None-Match": '"not-a-real-hash-value"'}
    )
    assert resp.status_code == 200


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

    trading_day = (base_ts + timedelta(days=34)).date()
    series = await load_price_series(db_pool, test_ticker)
    baseline = compute_baseline_as_of(test_ticker, series, trading_day)
    await upsert_baseline(db_pool, baseline)

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
    # z_score was computed from — not independently recomputed. Compared
    # with tolerance: the baselines table stores these as NUMERIC, which
    # rounds on write, so an exact float equality isn't guaranteed.
    assert abs(body["mean_return"] - baseline.mean_return_30d) < 1e-5
    assert abs(body["stdev_return"] - baseline.stdev_return_30d) < 1e-5


async def test_flagged_point_zscore_is_reproducible_from_response(client, db_pool, test_ticker):
    """The core correctness property of this screen: the displayed chart
    (mean_return, stdev_return, points) and the displayed z_score must be
    algebraically consistent — this is the one screen whose entire purpose
    is proving the system isn't a black box."""
    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    prices = [100.0 + i + (i % 3) * 0.7 for i in range(40)]  # non-trivial, still real, series
    await _seed_price_series(db_pool, test_ticker, base_ts, prices)

    # Flag an early day (index 10) — the rolling, look-ahead-safe baseline
    # for that day only has 9 prior returns to draw from (below the 30-day
    # cap, and below MIN_SAMPLE_SIZE — but evidence doesn't gate on that,
    # scoring already would have; this test only exercises the evidence
    # consistency invariant against whatever baseline row exists for that day).
    trading_day = (base_ts + timedelta(days=10)).date()
    series = await load_price_series(db_pool, test_ticker)
    baseline = compute_baseline_as_of(test_ticker, series, trading_day)
    await upsert_baseline(db_pool, baseline)

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


async def test_list_items_returns_watchlist_membership_not_just_flagged_tickers(
    client, db_pool, demo_watchlist, test_ticker, test_ticker_2
):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker_2})
    # Neither ticker has any flag at all — membership must still be visible.

    resp = await client.get(f"/watchlists/{demo_watchlist}/items")
    assert resp.status_code == 200
    tickers = {item["ticker"] for item in resp.json()}
    assert tickers == {test_ticker, test_ticker_2}
    sample = next(i for i in resp.json() if i["ticker"] == test_ticker)
    assert sample["name"] == "Test Ticker"
    assert sample["sector"] == "Test"


async def test_list_items_rejects_non_owned_watchlist(client, foreign_watchlist):
    resp = await client.get(f"/watchlists/{foreign_watchlist}/items")
    assert resp.status_code == 404


async def test_remove_item_deletes_from_watchlist(client, db_pool, demo_watchlist, test_ticker):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})
    row = await db_pool.fetchrow(
        "SELECT 1 FROM watchlist_items WHERE watchlist_id = $1 AND ticker = $2", demo_watchlist, test_ticker
    )
    assert row is not None

    resp = await client.delete(f"/watchlists/{demo_watchlist}/items/{test_ticker}")
    assert resp.status_code == 200

    row_after = await db_pool.fetchrow(
        "SELECT 1 FROM watchlist_items WHERE watchlist_id = $1 AND ticker = $2", demo_watchlist, test_ticker
    )
    assert row_after is None


async def test_remove_item_is_idempotent(client, demo_watchlist, test_ticker):
    # Never added — removing it anyway must be a no-op, not an error.
    resp = await client.delete(f"/watchlists/{demo_watchlist}/items/{test_ticker}")
    assert resp.status_code == 200

    resp_again = await client.delete(f"/watchlists/{demo_watchlist}/items/{test_ticker}")
    assert resp_again.status_code == 200


async def test_remove_item_rejects_non_owned_watchlist(client, foreign_watchlist, test_ticker):
    resp = await client.delete(f"/watchlists/{foreign_watchlist}/items/{test_ticker}")
    assert resp.status_code == 404
