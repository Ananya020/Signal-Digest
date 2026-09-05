from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import get_pool
from app.services.evidence import TickerMismatchError, build_evidence

router = APIRouter(prefix="/tickers", tags=["tickers"])


@router.get("")
async def list_tickers():
    """Universe metadata, not user data — no auth scoping needed."""
    pool = get_pool()
    rows = await pool.fetch("SELECT ticker, name, sector FROM tickers ORDER BY ticker ASC")
    return [{"ticker": row["ticker"], "name": row["name"], "sector": row["sector"]} for row in rows]


@router.get("/{ticker}/flags")
async def list_ticker_flags(ticker: str):
    """Historical audit trail for a ticker — every flag ever recorded for
    it, reverse chronological, independent of watchlist membership or
    whether it's currently unacknowledged. Distinct from `GET /digest`
    (current, unacked, watchlist-scoped): this is "what has this ticker
    been flagged for," not "what needs attention now." Universe-level, not
    user data — no auth/ownership scoping, same as `GET /tickers`."""
    pool = get_pool()

    ticker_row = await pool.fetchrow("SELECT ticker FROM tickers WHERE ticker = $1", ticker)
    if ticker_row is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    rows = await pool.fetch(
        """
        SELECT trading_day, signal_type, z_score, severity
        FROM flags
        WHERE ticker = $1
        ORDER BY trading_day DESC, computed_at DESC
        """,
        ticker,
    )
    return [
        {
            "trading_day": row["trading_day"].isoformat(),
            "signal_type": row["signal_type"],
            "z_score": float(row["z_score"]) if row["z_score"] is not None else None,
            "severity": row["severity"],
        }
        for row in rows
    ]


@router.get("/{ticker}/evidence")
async def get_evidence(ticker: str, flag_id: int, _user_id=Depends(get_current_user)):
    pool = get_pool()

    ticker_row = await pool.fetchrow("SELECT ticker FROM tickers WHERE ticker = $1", ticker)
    if ticker_row is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    try:
        evidence = await build_evidence(pool, ticker, flag_id)
    except TickerMismatchError:
        raise HTTPException(status_code=400, detail="flag_id does not belong to this ticker")

    if evidence is None:
        raise HTTPException(status_code=404, detail="Flag or evidence not found")

    return evidence
