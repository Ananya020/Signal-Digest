import uuid

import asyncpg
import httpx
import pytest
import pytest_asyncio

from app.auth import DEMO_USER_ID
from app.config import settings


@pytest_asyncio.fixture
async def db_pool():
    try:
        pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable at {settings.database_url}: {e}")
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def test_ticker(db_pool):
    """A throwaway ticker row, cleaned up after the test, so ingestion tests
    don't collide with real seeded data or leave residue."""
    symbol = "ZZTEST.NS"
    await db_pool.execute(
        "INSERT INTO tickers (ticker, name, sector) VALUES ($1, $2, $3) "
        "ON CONFLICT (ticker) DO NOTHING",
        symbol,
        "Test Ticker",
        "Test",
    )
    yield symbol
    # flags/flag_ack/watchlist_items FK-reference tickers — must clear those
    # first. watchlist_items rows are created by Phase 3 tests via the API
    # (no fixture "owns" them), and fixture teardown order isn't guaranteed
    # relative to the watchlist fixture's own cleanup, so this fixture must
    # defensively clear them itself before deleting the ticker.
    await db_pool.execute(
        "DELETE FROM flag_ack WHERE flag_id IN (SELECT id FROM flags WHERE ticker = $1)", symbol
    )
    await db_pool.execute("DELETE FROM flags WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM watchlist_items WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM baselines WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM price_ticks WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM tickers WHERE ticker = $1", symbol)


@pytest_asyncio.fixture
async def test_watchlist(db_pool):
    """A throwaway watchlist row (random, non-demo owner) for flag_ack
    transaction tests, cleaned up after."""
    watchlist_id = uuid.uuid4()
    await db_pool.execute(
        "INSERT INTO watchlists (id, user_id, name) VALUES ($1, $2, $3)",
        watchlist_id, uuid.uuid4(), "Test Watchlist",
    )
    yield watchlist_id
    await db_pool.execute("DELETE FROM flag_ack WHERE watchlist_id = $1", watchlist_id)
    await db_pool.execute("DELETE FROM watchlists WHERE id = $1", watchlist_id)


async def _make_watchlist(db_pool, user_id: uuid.UUID, name: str) -> uuid.UUID:
    watchlist_id = uuid.uuid4()
    await db_pool.execute(
        "INSERT INTO watchlists (id, user_id, name) VALUES ($1, $2, $3)",
        watchlist_id, user_id, name,
    )
    return watchlist_id


async def _cleanup_watchlist(db_pool, watchlist_id: uuid.UUID) -> None:
    await db_pool.execute("DELETE FROM flag_ack WHERE watchlist_id = $1", watchlist_id)
    await db_pool.execute("DELETE FROM watchlist_items WHERE watchlist_id = $1", watchlist_id)
    await db_pool.execute("DELETE FROM watchlists WHERE id = $1", watchlist_id)


@pytest_asyncio.fixture
async def demo_watchlist(db_pool):
    """A watchlist owned by the Phase 3 demo user (app.auth.DEMO_USER_ID) —
    accessible through the API's real get_current_user() dependency."""
    watchlist_id = await _make_watchlist(db_pool, DEMO_USER_ID, "Demo Watchlist")
    yield watchlist_id
    await _cleanup_watchlist(db_pool, watchlist_id)


@pytest_asyncio.fixture
async def demo_watchlist_2(db_pool):
    """A second, separate demo-owned watchlist, for cross-watchlist
    isolation tests."""
    watchlist_id = await _make_watchlist(db_pool, DEMO_USER_ID, "Demo Watchlist 2")
    yield watchlist_id
    await _cleanup_watchlist(db_pool, watchlist_id)


@pytest_asyncio.fixture
async def foreign_watchlist(db_pool):
    """A watchlist owned by someone other than the demo user, for
    ownership-rejection tests."""
    watchlist_id = await _make_watchlist(db_pool, uuid.uuid4(), "Not The Demo User's Watchlist")
    yield watchlist_id
    await _cleanup_watchlist(db_pool, watchlist_id)


@pytest_asyncio.fixture
async def test_ticker_2(db_pool):
    """A second throwaway ticker, for cross-watchlist isolation tests that
    need two distinct tickers."""
    symbol = "ZZTEST2.NS"
    await db_pool.execute(
        "INSERT INTO tickers (ticker, name, sector) VALUES ($1, $2, $3) "
        "ON CONFLICT (ticker) DO NOTHING",
        symbol, "Test Ticker 2", "Test",
    )
    yield symbol
    await db_pool.execute(
        "DELETE FROM flag_ack WHERE flag_id IN (SELECT id FROM flags WHERE ticker = $1)", symbol
    )
    await db_pool.execute("DELETE FROM flags WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM watchlist_items WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM baselines WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM price_ticks WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM tickers WHERE ticker = $1", symbol)


@pytest_asyncio.fixture
async def client(db_pool):
    """httpx AsyncClient wired directly to the FastAPI app via ASGI
    transport (no real server process), with the app's own lifespan
    (DB pool connect/disconnect, provider construction) run around it.

    The live background scheduler is disabled for this fixture — tests
    exercise scoring via `run_scoring_cycle` directly (deterministic, no
    race against a real 5s-interval job), never through the actual
    APScheduler loop. `app.state.provider` is still fully constructed and
    usable (digest/status endpoints work normally)."""
    from app.config import settings
    from app.main import app

    previous = settings.scheduler_enabled
    settings.scheduler_enabled = False
    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
    finally:
        settings.scheduler_enabled = previous
