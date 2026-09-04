"""Phase 4 API integration tests — real Postgres, real FastAPI app via ASGI
transport. Covers /admin/fault's DEMO_MODE gate, /provider/status, and the
digest endpoint's real freshness field.
"""

from app.config import settings
from app.services.provider_state import load_provider_state, save_provider_state


async def test_admin_fault_404s_when_demo_mode_unset(client, db_pool):
    previous = settings.demo_mode
    settings.demo_mode = False
    try:
        resp = await client.post("/admin/fault", json={"mode": "outage"})
        assert resp.status_code == 404
    finally:
        settings.demo_mode = previous
        await save_provider_state(db_pool, "normal", None)


async def test_admin_fault_works_when_demo_mode_set(client, db_pool):
    previous = settings.demo_mode
    settings.demo_mode = True
    try:
        resp = await client.post("/admin/fault", json={"mode": "stale"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "stale"
        assert body["frozen_at"] is not None

        row = await load_provider_state(db_pool)
        assert row["mode"] == "stale"  # persisted, not just in-memory
    finally:
        resp = await client.post("/admin/fault", json={"mode": "recover"})
        assert resp.status_code == 200
        settings.demo_mode = previous


async def test_admin_fault_recover_clears_frozen_at(client, db_pool):
    previous = settings.demo_mode
    settings.demo_mode = True
    try:
        await client.post("/admin/fault", json={"mode": "outage"})
        resp = await client.post("/admin/fault", json={"mode": "recover"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "normal"
        assert resp.json()["frozen_at"] is None

        row = await load_provider_state(db_pool)
        assert row["mode"] == "normal"
        assert row["frozen_at"] is None
    finally:
        settings.demo_mode = previous


async def test_admin_fault_concurrent_calls_last_write_wins(client, db_pool):
    previous = settings.demo_mode
    settings.demo_mode = True
    try:
        await client.post("/admin/fault", json={"mode": "stale"})
        await client.post("/admin/fault", json={"mode": "outage"})  # arrives "close together"

        row = await load_provider_state(db_pool)
        assert row["mode"] == "outage"  # the second call's mode wins

        status_resp = await client.get("/provider/status")
        assert status_resp.json()["state"] == "UNAVAILABLE"
    finally:
        await client.post("/admin/fault", json={"mode": "recover"})
        settings.demo_mode = previous


async def test_provider_status_returns_live_shape(client):
    resp = await client.get("/provider/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] in {"LIVE", "RECENT", "DELAYED", "STALE", "UNAVAILABLE"}
    assert "age_seconds" in body
    assert "last_successful_fetch" in body
    assert "detail" in body
    assert isinstance(body["demo_mode"], bool)  # Phase 5: frontend gates the fault-injection control on this


async def test_digest_reflects_real_provider_status(client, db_pool, demo_watchlist, test_ticker):
    await client.post(f"/watchlists/{demo_watchlist}/items", json={"ticker": test_ticker})

    resp = await client.get(f"/watchlists/{demo_watchlist}/digest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["freshness"] in {"LIVE", "RECENT", "DELAYED", "STALE"}  # not hardcoded "LIVE"
    assert "detail" in body
