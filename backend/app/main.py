from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import connect_db, disconnect_db, get_pool
from app.providers.fault_injecting import FaultInjectingProvider
from app.providers.historical_replay import HistoricalReplayProvider, ReplayClock, load_history
from app.routers import admin, health, provider_status, tickers, watchlists
from app.services.scoring_pipeline import ALL_TICKERS, SECTOR_BY_NSE_TICKER, run_scoring_cycle


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    pool = get_pool()

    history = await load_history(pool, ALL_TICKERS)
    base_provider = HistoricalReplayProvider(history=history, clock=ReplayClock(start_step=1))
    provider = FaultInjectingProvider(
        wrapped=base_provider,
        live_seconds=settings.freshness_live_seconds,
        recent_seconds=settings.freshness_recent_seconds,
        delayed_seconds=settings.freshness_delayed_seconds,
        stale_seconds=settings.freshness_stale_seconds,
    )
    await provider.sync_from_db(pool)  # restore fault mode across a process restart
    app.state.provider = provider

    scheduler = AsyncIOScheduler()

    async def scheduled_tick() -> None:
        try:
            await run_scoring_cycle(pool, provider, ALL_TICKERS, SECTOR_BY_NSE_TICKER)
        except Exception as e:  # noqa: BLE001 — the scheduler must never crash the app
            print(f"[scheduler] tick error: {e}")
        finally:
            # Always call advance() — it's a no-op internally whenever the
            # provider is frozen (fault mode 'outage'/'stale'), so the
            # scheduler itself never branches on fault state.
            provider.advance()
            # Keep provider_state's last_successful_fetch in sync every
            # tick, so an unclean crash loses at most one interval's worth
            # of freshness-age precision on restart, not the whole outage.
            try:
                await provider.persist(pool)
            except Exception as e:  # noqa: BLE001
                print(f"[scheduler] persist error: {e}")

    if settings.scheduler_enabled:
        scheduler.add_job(scheduled_tick, "interval", seconds=settings.scheduler_interval_seconds, id="scoring_tick")
        scheduler.start()
    app.state.scheduler = scheduler

    yield

    if settings.scheduler_enabled:
        scheduler.shutdown(wait=False)
    await disconnect_db()


app = FastAPI(title="Signal Digest", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(watchlists.router)
app.include_router(tickers.router)
app.include_router(admin.router)
app.include_router(provider_status.router)
