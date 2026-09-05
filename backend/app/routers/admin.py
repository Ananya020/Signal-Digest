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
    code with it.

    **Deployment hardening (additive, not a replacement for the DEMO_MODE
    gate above):** when DEMO_SECRET is set — intended for a public
    deployment (Render), never for local dev — the caller must also present
    the exact same value, via either the `X-Demo-Secret` header or a
    `demo_secret` query param. A missing/wrong secret 404s identically to
    the DEMO_MODE gate's own failure, so a public deployment can't be probed
    to distinguish "wrong secret" from "endpoint doesn't exist." When
    DEMO_SECRET is unset (the default, matching .env.example / local dev
    unchanged), this check is skipped entirely — behavior is byte-for-byte
    identical to before this hardening existed."""
    if not settings.demo_mode:
        raise HTTPException(status_code=404)

    if settings.demo_secret:
        provided = request.headers.get("x-demo-secret") or request.query_params.get("demo_secret")
        if provided != settings.demo_secret:
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
