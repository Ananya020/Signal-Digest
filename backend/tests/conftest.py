import uuid

import asyncpg
import pytest
import pytest_asyncio

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
    # flags/flag_ack FK-reference tickers — must clear those first (Phase 2)
    await db_pool.execute(
        "DELETE FROM flag_ack WHERE flag_id IN (SELECT id FROM flags WHERE ticker = $1)", symbol
    )
    await db_pool.execute("DELETE FROM flags WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM baselines WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM price_ticks WHERE ticker = $1", symbol)
    await db_pool.execute("DELETE FROM tickers WHERE ticker = $1", symbol)


@pytest_asyncio.fixture
async def test_watchlist(db_pool):
    """A throwaway watchlist row for flag_ack tests, cleaned up after."""
    watchlist_id = uuid.uuid4()
    await db_pool.execute(
        "INSERT INTO watchlists (id, user_id, name) VALUES ($1, $2, $3)",
        watchlist_id, uuid.uuid4(), "Test Watchlist",
    )
    yield watchlist_id
    await db_pool.execute("DELETE FROM flag_ack WHERE watchlist_id = $1", watchlist_id)
    await db_pool.execute("DELETE FROM watchlists WHERE id = $1", watchlist_id)
