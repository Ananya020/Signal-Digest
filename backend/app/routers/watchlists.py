import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth import get_current_user
from app.db import get_pool
from app.schemas import AckRequest, WatchlistCreate, WatchlistItemCreate
from app.services.digest import compute_digest
from app.services.watchlist_access import get_owned_watchlist

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _quoted(etag_hash: str) -> str:
    return f'"{etag_hash}"'


def _normalize_if_none_match(header_value: str) -> str:
    value = header_value.strip()
    if value.startswith("W/"):
        value = value[2:].strip()
    return value.strip('"')


def _serialize_flag(row) -> dict:
    return {
        "id": row["id"],
        "ticker": row["ticker"],
        "trading_day": row["trading_day"].isoformat(),
        "signal_type": row["signal_type"],
        "z_score": float(row["z_score"]) if row["z_score"] is not None else None,
        "severity": row["severity"],
        "severity_rank": row["severity_rank"],
        "volume_ratio": float(row["volume_ratio"]) if row["volume_ratio"] is not None else None,
        "sector_relative": row["sector_relative"],
        "computed_at": row["computed_at"].isoformat(),
        "provider_state_at_computation": row["provider_state_at_computation"],
    }


@router.get("")
async def list_watchlists(user_id: uuid.UUID = Depends(get_current_user)):
    """Ownership-scoped — same pattern as every other watchlist endpoint,
    just via WHERE user_id = $1 rather than a single-row lookup."""
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT id, name, created_at FROM watchlists WHERE user_id = $1 ORDER BY created_at ASC",
        user_id,
    )
    return [
        {"id": str(row["id"]), "name": row["name"], "created_at": row["created_at"].isoformat()}
        for row in rows
    ]


@router.post("", status_code=201)
async def create_watchlist(payload: WatchlistCreate, user_id: uuid.UUID = Depends(get_current_user)):
    pool = get_pool()
    watchlist_id = uuid.uuid4()
    await pool.execute(
        "INSERT INTO watchlists (id, user_id, name) VALUES ($1, $2, $3)",
        watchlist_id, user_id, payload.name,
    )
    return {"id": str(watchlist_id), "user_id": str(user_id), "name": payload.name}


@router.post("/{watchlist_id}/items")
async def add_watchlist_item(
    watchlist_id: uuid.UUID, payload: WatchlistItemCreate, user_id: uuid.UUID = Depends(get_current_user)
):
    pool = get_pool()
    await get_owned_watchlist(pool, watchlist_id, user_id)

    ticker_row = await pool.fetchrow("SELECT ticker FROM tickers WHERE ticker = $1", payload.ticker)
    if ticker_row is None:
        raise HTTPException(status_code=422, detail=f"Unknown ticker: {payload.ticker}")

    await pool.execute(
        "INSERT INTO watchlist_items (watchlist_id, ticker) VALUES ($1, $2) "
        "ON CONFLICT (watchlist_id, ticker) DO NOTHING",
        watchlist_id, payload.ticker,
    )
    return {"watchlist_id": str(watchlist_id), "ticker": payload.ticker}


@router.get("/{watchlist_id}/items")
async def list_watchlist_items(watchlist_id: uuid.UUID, user_id: uuid.UUID = Depends(get_current_user)):
    """Watchlist ticker membership — {ticker, name, sector} — independent
    of whether a ticker currently has an active flag (the digest only
    returns flagged tickers, which isn't the same as membership)."""
    pool = get_pool()
    await get_owned_watchlist(pool, watchlist_id, user_id)

    rows = await pool.fetch(
        """
        SELECT t.ticker, t.name, t.sector
        FROM watchlist_items wi
        JOIN tickers t ON t.ticker = wi.ticker
        WHERE wi.watchlist_id = $1
        ORDER BY t.ticker ASC
        """,
        watchlist_id,
    )
    return [{"ticker": row["ticker"], "name": row["name"], "sector": row["sector"]} for row in rows]


@router.delete("/{watchlist_id}/items/{ticker}")
async def remove_watchlist_item(watchlist_id: uuid.UUID, ticker: str, user_id: uuid.UUID = Depends(get_current_user)):
    """Idempotent — removing a ticker not currently in the watchlist is a
    no-op, not an error, same idempotency stance as POST /items."""
    pool = get_pool()
    await get_owned_watchlist(pool, watchlist_id, user_id)

    await pool.execute(
        "DELETE FROM watchlist_items WHERE watchlist_id = $1 AND ticker = $2",
        watchlist_id, ticker,
    )
    return {"watchlist_id": str(watchlist_id), "ticker": ticker}


@router.get("/{watchlist_id}/digest")
async def get_digest(
    watchlist_id: uuid.UUID, request: Request, response: Response, user_id: uuid.UUID = Depends(get_current_user)
):
    pool = get_pool()
    await get_owned_watchlist(pool, watchlist_id, user_id)

    aggregate_hash, rows = await compute_digest(pool, watchlist_id)
    response.headers["ETag"] = _quoted(aggregate_hash)

    if_none_match = request.headers.get("if-none-match")
    if if_none_match and _normalize_if_none_match(if_none_match) == aggregate_hash:
        return Response(status_code=304, headers={"ETag": _quoted(aggregate_hash)})

    provider = request.app.state.provider
    provider_status = provider.get_status()

    # UNAVAILABLE: still return the last-known unacked flags (never empty
    # the response), but never compute/fabricate anything new — the freshness
    # field + detail make it explicit that no new scoring occurred this cycle.
    return {
        "freshness": provider_status.state,
        "detail": provider_status.detail,
        "flags": [_serialize_flag(row) for row in rows],
    }


@router.post("/{watchlist_id}/ack")
async def ack_flags(watchlist_id: uuid.UUID, payload: AckRequest, user_id: uuid.UUID = Depends(get_current_user)):
    pool = get_pool()
    await get_owned_watchlist(pool, watchlist_id, user_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Existence check before insert (RELIABILITY.md #14): a
            # deleted/superseded flag_id is ignored, not a hard failure for
            # the whole request.
            existing = await conn.fetch(
                "SELECT id FROM flags WHERE id = ANY($1::bigint[])", payload.flag_ids
            )
            valid_ids = [row["id"] for row in existing]
            for flag_id in valid_ids:
                await conn.execute(
                    "INSERT INTO flag_ack (flag_id, watchlist_id, acked_at) VALUES ($1, $2, now()) "
                    "ON CONFLICT (flag_id, watchlist_id) DO NOTHING",
                    flag_id, watchlist_id,
                )

    # Server is authoritative — always recompute from committed state,
    # never trust a client-supplied hash.
    aggregate_hash, _ = await compute_digest(pool, watchlist_id)
    valid_id_set = set(valid_ids)
    ignored = [
        {"id": fid, "reason": "flag_not_found"}
        for fid in payload.flag_ids
        if fid not in valid_id_set
    ]
    return {"acked": valid_ids, "ignored": ignored, "hash": aggregate_hash}
