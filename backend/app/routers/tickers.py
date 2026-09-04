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
