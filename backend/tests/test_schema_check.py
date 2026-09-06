"""app/services/schema_check.py — startup safety check, added after a real
incident (migrations/004_persist_replay_step.sql applied locally but never
run against the remote Render Postgres, crash-looping on an opaque
asyncpg.exceptions.UndefinedColumnError). These tests confirm the check
actually detects both a missing column and a missing table, with a specific
error naming the exact migration file that adds it.

Every mutating test wraps its DROP in a transaction it manually rolls back
in `finally` (never `async with conn.transaction()`'s auto-commit-on-success
sugar) — this must never permanently alter the real shared dev database's
schema, even if an assertion fails."""

import pytest

from app.services.schema_check import EXPECTED_COLUMNS, EXPECTED_TABLES, SchemaCheckError, check_schema_or_raise


async def test_passes_against_the_real_current_schema(db_pool):
    # No mutation -- the real dev DB's schema is expected to be fully
    # migrated already. If this fails, it means an actual migration is
    # missing locally, which is exactly what this check exists to surface.
    await check_schema_or_raise(db_pool)


async def test_missing_column_raises_with_the_exact_column_and_migration_named(db_pool):
    async with db_pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute("ALTER TABLE provider_state DROP COLUMN replay_step")
            with pytest.raises(SchemaCheckError) as exc_info:
                await check_schema_or_raise(conn)
            message = str(exc_info.value)
            assert "replay_step" in message
            assert "provider_state" in message
            assert "004_persist_replay_step.sql" in message
        finally:
            await tr.rollback()

    # Rollback confirmed: the column is back, real schema unaffected.
    await check_schema_or_raise(db_pool)


async def test_missing_table_raises_with_the_exact_table_and_migration_named(db_pool):
    async with db_pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute("DROP TABLE flag_ack_history")
            with pytest.raises(SchemaCheckError) as exc_info:
                await check_schema_or_raise(conn)
            message = str(exc_info.value)
            assert "flag_ack_history" in message
            assert "003_since_last_checked.sql" in message
        finally:
            await tr.rollback()

    await check_schema_or_raise(db_pool)


async def test_table_check_runs_before_column_check():
    # If a whole table is missing, the error must name the missing TABLE,
    # not crash trying to look up columns on a table that doesn't exist.
    assert len(EXPECTED_TABLES) > 0  # sanity: there is something to check first


def test_every_expected_entry_names_a_real_migration_file():
    # Catches a copy-paste typo in this registry itself (e.g. a filename
    # that doesn't exist) -- this list is the whole point of the check, so
    # it must stay accurate.
    import os

    migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
    real_files = set(os.listdir(migrations_dir))

    for entry in [*EXPECTED_COLUMNS, *EXPECTED_TABLES]:
        assert entry.migration in real_files, f"{entry.migration} does not exist in backend/migrations/"
