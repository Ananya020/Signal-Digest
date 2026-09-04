from fastapi import APIRouter, Request

router = APIRouter(tags=["provider"])


@router.get("/provider/status")
async def get_provider_status(request: Request):
    """`age_seconds` is computed live from real wall-clock time on every
    call, never cached — polled by the frontend for the freshness banner
    (Phase 5)."""
    provider = request.app.state.provider
    status = provider.get_status()
    return {
        "state": status.state,
        "last_successful_fetch": status.last_successful_fetch.isoformat(),
        "age_seconds": status.age_seconds,
        "detail": status.detail,
    }
