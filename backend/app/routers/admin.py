from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.db import get_pool

router = APIRouter(tags=["admin"])


class FaultRequest(BaseModel):
    mode: Literal["outage", "stale", "recover"]


@router.post("/admin/fault")
async def set_fault_mode(payload: FaultRequest, request: Request):
    """Demo-only. Hard-gated behind DEMO_MODE at the route level — 404s
    unconditionally if unset, before touching the provider or DB, so this
    can never be reached by calling some other route that happens to share
    code with it."""
    if not settings.demo_mode:
        raise HTTPException(status_code=404)

    provider = request.app.state.provider
    new_mode = "normal" if payload.mode == "recover" else payload.mode
    provider.set_mode(new_mode)

    # Last-write-wins: a single UPSERT on the fixed id=1 row, no locking
    # (Phase 4 locked decision — this is a demo-only endpoint operated by
    # one person at a time). persist() writes mode/frozen_at AND
    # last_successful_fetch together, so a restart's freshness state is
    # correctly restored (see fault_injecting.py's module docstring).
    pool = get_pool()
    await provider.persist(pool)

    return {
        "mode": new_mode,
        "frozen_at": provider.frozen_at.isoformat() if provider.frozen_at else None,
    }
