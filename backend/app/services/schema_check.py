"""Startup-only schema safety check (called from app/main.py's lifespan,
before the scheduler or any request handling starts).

Real incident this exists for (2026-09-06): migrations/004_persist_replay_step.sql
was applied locally and shipped in the deployed code, but never run against
the remote Render Postgres. The app crash-looped on boot with:

    asyncpg.exceptions.UndefinedColumnError: column "replay_step" does not exist

...several stack frames deep inside FastAPI's merged lifespan machinery —
correct, but not actionable at a glance. This check runs first and fails
with a one-line, specific error naming the missing table/column and the
exact migration file that adds it, so the same mistake next time reads like
an instruction, not a puzzle.

This does NOT fix a missing migration and is NOT a migration runner — it
only detects the gap early. The fix is still: run the named migration file
against the real database (see DEPLOYMENT.md's migration runbook).

Only covers schema additions AFTER 001_init.sql's baseline. 001_init.sql
itself is not checked here — if it were never applied, essentially every
query in the app would fail immediately and obviously; this list exists
specifically for the "quietly forgot to run migration N" failure mode, which
is exactly what makes a *later* migration easy to forget while everything
else keeps working.

Keeping this in sync with migrations/ is manual, by design — there is no
migration-tracking table in this project (see DATA_MODEL.md), so nothing
else could compute this automatically without adding one. Add an entry here
in the same commit as any future migration that adds a column or table an
existing code path reads.
"""

from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True)
class ExpectedColumn:
    table: str
    column: str
    migration: str


@dataclass(frozen=True)
class ExpectedTable:
    table: str
    migration: str


# Every column added by a migration after 001_init.sql's baseline schema.
EXPECTED_COLUMNS: list[ExpectedColumn] = [
    ExpectedColumn("provider_state", "last_successful_fetch", "002_add_last_successful_fetch.sql"),
    ExpectedColumn("flag_ack", "severity_rank_at_ack", "003_since_last_checked.sql"),
    ExpectedColumn("flag_ack", "z_score_at_ack", "003_since_last_checked.sql"),
    ExpectedColumn("provider_state", "replay_step", "004_persist_replay_step.sql"),
]

# Tables created wholesale by a migration after 001_init.sql — a missing
# column check can't catch a missing table (there'd be no table to look a
# column up on), so table existence is checked separately, first.
EXPECTED_TABLES: list[ExpectedTable] = [
    ExpectedTable("flag_ack_history", "003_since_last_checked.sql"),
]


class SchemaCheckError(RuntimeError):
    """Raised at startup when the connected database is missing a table or
    column the deployed code expects — see this module's docstring."""


async def check_schema_or_raise(pool: asyncpg.Pool | asyncpg.Connection) -> None:
    """`pool` may be a Pool (real startup use) or a single Connection (tests
    that need to run this inside a transaction they control) — both expose
    the same `.fetch()` interface this function relies on."""
    existing_tables = {
        row["table_name"]
        for row in await pool.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    }

    missing_tables = [t for t in EXPECTED_TABLES if t.table not in existing_tables]
    if missing_tables:
        first = missing_tables[0]
        raise SchemaCheckError(
            f"Database schema is out of date: table '{first.table}' does not exist. "
            f"Run migrations/{first.migration} against this database before starting the "
            f"app — see DEPLOYMENT.md's migration runbook."
        )

    existing_columns = {
        (row["table_name"], row["column_name"])
        for row in await pool.fetch(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
        )
    }

    missing_columns = [c for c in EXPECTED_COLUMNS if (c.table, c.column) not in existing_columns]
    if missing_columns:
        first = missing_columns[0]
        suffix = f" ({len(missing_columns) - 1} other column(s) also missing)" if len(missing_columns) > 1 else ""
        raise SchemaCheckError(
            f"Database schema is out of date: column '{first.column}' does not exist on table "
            f"'{first.table}'{suffix}. Run migrations/{first.migration} against this database "
            f"before starting the app — see DEPLOYMENT.md's migration runbook."
        )
