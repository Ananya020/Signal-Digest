"""Phase 5 STEP 1 — two new thin list endpoints, tested against real
Postgres via the existing httpx ASGI client fixture."""


async def test_list_watchlists_is_ownership_scoped(client, demo_watchlist, foreign_watchlist):
    resp = await client.get("/watchlists")
    assert resp.status_code == 200
    body = resp.json()
    ids = {w["id"] for w in body}

    assert str(demo_watchlist) in ids       # demo user's own watchlist is listed
    assert str(foreign_watchlist) not in ids  # someone else's watchlist is not


async def test_list_watchlists_shape(client, demo_watchlist):
    resp = await client.get("/watchlists")
    body = resp.json()
    match = next(w for w in body if w["id"] == str(demo_watchlist))
    assert match["name"] == "Demo Watchlist"
    assert "created_at" in match


async def test_list_tickers_returns_full_universe(client):
    resp = await client.get("/tickers")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 34  # current real seeded universe (TATAMOTORS.NS absent, see PROGRESS.md)
    sample = next(t for t in body if t["ticker"] == "RELIANCE.NS")
    assert sample["sector"] == "Energy/Materials"
    assert sample["name"]


async def test_list_tickers_requires_no_auth(client):
    # Universe metadata, not user data — no Depends(get_current_user) side
    # effect should block this; just confirming it isn't 401/403/404.
    resp = await client.get("/tickers")
    assert resp.status_code == 200
