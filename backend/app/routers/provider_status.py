from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.services.scoring_pipeline import ALL_TICKERS

router = APIRouter(tags=["provider"])


@router.get("/provider/status")
async def get_provider_status(request: Request):
    """`age_seconds` is computed live from real wall-clock time on every
    call, never cached — polled by the frontend for the freshness banner
    (Phase 5). `demo_mode` tells the frontend whether to render the
    fault-injection control at all, without guessing or hardcoding —
    the same DEMO_MODE flag /admin/fault itself is gated behind."""
    provider = request.app.state.provider
    status = provider.get_status()
    return {
        "state": status.state,
        "last_successful_fetch": status.last_successful_fetch.isoformat(),
        "age_seconds": status.age_seconds,
        "detail": status.detail,
        "demo_mode": settings.demo_mode,
    }


@router.get("/provider/live-status")
async def get_live_provider_status(request: Request, ticker: str | None = None):
    """Workstream 3 — opt-in, additive-only. Hard-gated behind
    LIVE_PROVIDER_ENABLED at the route level, same convention as
    /admin/fault's DEMO_MODE gate: 404s unconditionally when the flag is
    unset, before touching the provider, so this is provably inert by
    default (the route doesn't meaningfully exist). Orthogonal to
    DEMO_MODE — this flag alone controls it.

    Attempts one real fetch on every call (`get_ticks` for the requested
    ticker, then `get_status`) — status-only, never wired into scoring/
    baselines. A failed/malformed fetch surfaces as UNAVAILABLE/STALE
    through the exact same freshness state machine every other provider
    uses, not a special error response."""
    if not settings.live_provider_enabled:
        raise HTTPException(status_code=404)

    provider = request.app.state.live_provider
    target = ticker or ALL_TICKERS[0]
    ticks = provider.get_ticks([target])
    status = provider.get_status()

    return {
        "state": status.state,
        "last_successful_fetch": status.last_successful_fetch.isoformat(),
        "age_seconds": status.age_seconds,
        "detail": status.detail,
        "tick": ticks[0].model_dump(mode="json") if ticks else None,
    }
