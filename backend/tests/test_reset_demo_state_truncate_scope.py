"""Regression coverage for a real bug: reset_demo_state.py's TRUNCATE list
was never updated when flag_ack_history (migrations/003_since_last_checked.sql)
was added with a foreign key into flags — the script then failed against the
real Render DB with FeatureNotSupportedError the first time flag_ack_history
actually had rows, since Postgres requires every table with an FK into a
truncated table to be included in the same TRUNCATE (or CASCADE).

This test would have caught it: it introspects the real schema for every
table with a foreign key into any table reset_demo_state.py truncates, and
asserts the referencing table is itself in that same truncate list. It is
schema-driven, not a hardcoded list of today's known tables, so a *future*
new table with an FK into flags/flag_ack/flag_ack_history/watchlist_ack_state
that isn't added to TRUNCATE_TABLES will fail this test the same way.
"""

from scripts.reset_demo_state import TRUNCATE_TABLES


async def test_every_table_with_an_fk_into_a_truncated_table_is_itself_truncated(db_pool):
    rows = await db_pool.fetch(
        """
        SELECT
            tc.table_name AS referencing_table,
            ccu.table_name AS referenced_table
        FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        """
    )

    truncated = set(TRUNCATE_TABLES)
    missing = [
        (row["referencing_table"], row["referenced_table"])
        for row in rows
        if row["referenced_table"] in truncated and row["referencing_table"] not in truncated
    ]

    assert missing == [], (
        f"These tables have a foreign key into a table reset_demo_state.py truncates, "
        f"but are not themselves in TRUNCATE_TABLES — TRUNCATE will fail against a real "
        f"Postgres DB once they have rows: {missing}"
    )
