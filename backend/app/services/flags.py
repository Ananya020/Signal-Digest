"""Flag persistence with the severity-escalation ack-bust rule from
DATA_MODEL.md — the one correctness rule in the project that must never
regress (CLAUDE.md).

## Correction to DATA_MODEL.md's literal SQL (documented per CLAUDE.md's
## rule on deviating from a locked decision — do not silently pretend the
## original was still correct)

DATA_MODEL.md's original upsert used:

    ON CONFLICT (...) DO UPDATE SET ...
    WHERE EXCLUDED.severity_rank IS DISTINCT FROM flags.severity_rank
       OR flags.severity_rank IS NULL
    RETURNING id, severity_rank, (xmax = 0) AS was_insert

Verified directly against real Postgres (see test_flags_ack_bust.py /
manual scratch verification): when this `WHERE` evaluates false on a
conflict, `RETURNING` yields **zero rows** — not the old row, not a partial
update. That single `WHERE` clause was conflating two distinct questions:

  1. "Should this flag's stored evidence (z_score, volume_ratio,
     sector_relative, computed_at, provider_state_at_computation) be
     refreshed to the latest computation?"
  2. "Should an existing acknowledgement be busted?"

Gating BOTH on "did severity_rank change" meant a same-severity rerun (e.g.
z_score drifting from 2.1 to 2.4, still `notable`) skipped the update
entirely — the flag's evidence went stale even though a genuinely newer
computation had just run. A flag must always represent the latest
computation; only the ack-bust decision is conditional on severity_rank.

**Corrected design**: the `ON CONFLICT DO UPDATE` always fires and always
refreshes every evidence column (unconditional `SET`, no `WHERE`). The
ack-bust decision is made separately, in the same transaction, by comparing
the severity_rank read *before* the upsert against the new one:

    new_rank > previous_rank  -> delete flag_ack (escalation busts ack)
    new_rank == previous_rank -> leave flag_ack untouched
    new_rank <  previous_rank -> leave flag_ack untouched (de-escalation)
    no previous row (first insert) -> nothing to bust

This preserves the intended ack-bust semantics from DATA_MODEL.md exactly,
while fixing the stale-evidence defect. Still one atomic `conn.transaction()`
— the previous-rank read, the upsert, and the conditional delete are never
split across separate transactions.
"""

from dataclasses import dataclass

import asyncpg

from app.services.scoring import FlagCandidate

_UPSERT_SQL = """
    INSERT INTO flags (
        ticker, trading_day, signal_type, z_score, severity, severity_rank,
        volume_ratio, sector_relative, computed_at, provider_state_at_computation
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    ON CONFLICT (ticker, trading_day, signal_type) DO UPDATE
    SET z_score = EXCLUDED.z_score, severity = EXCLUDED.severity,
        severity_rank = EXCLUDED.severity_rank, volume_ratio = EXCLUDED.volume_ratio,
        sector_relative = EXCLUDED.sector_relative, computed_at = EXCLUDED.computed_at,
        provider_state_at_computation = EXCLUDED.provider_state_at_computation
    RETURNING id, severity_rank, (xmax = 0) AS was_insert
"""


@dataclass
class UpsertResult:
    id: int
    severity_rank: int
    was_insert: bool
    ack_busted: bool


async def upsert_flag_with_ack_bust(conn: asyncpg.Connection, candidate: FlagCandidate) -> UpsertResult:
    """`conn` must be a single acquired connection (not a pool) — the
    transaction below is the atomicity boundary DATA_MODEL.md requires.

    Every call unconditionally refreshes the flag's evidence columns to the
    latest computation. Ack-busting is decided independently, by comparing
    the severity_rank read before the upsert to the new one."""
    async with conn.transaction():
        previous = await conn.fetchrow(
            "SELECT severity_rank FROM flags WHERE ticker = $1 AND trading_day = $2 AND signal_type = $3",
            candidate.ticker, candidate.trading_day, candidate.signal_type,
        )
        previous_rank = previous["severity_rank"] if previous else None

        row = await conn.fetchrow(
            _UPSERT_SQL,
            candidate.ticker,
            candidate.trading_day,
            candidate.signal_type,
            candidate.z_score,
            candidate.severity,
            candidate.severity_rank,
            candidate.volume_ratio,
            candidate.sector_relative,
            candidate.computed_at,
            candidate.provider_state_at_computation,
        )
        # Unconditional SET with no WHERE guarantees a row is always
        # returned here — asserted, not just assumed, since a silent
        # None here would be exactly the class of bug this module exists
        # to prevent.
        assert row is not None, "unconditional ON CONFLICT DO UPDATE must always return a row"

        flag_id = row["id"]
        new_rank = row["severity_rank"]
        was_insert = row["was_insert"]

        ack_busted = False
        if not was_insert and previous_rank is not None and new_rank > previous_rank:
            # Step A ("since you last checked"): snapshot the live ack row
            # into the audit-only history table immediately before deleting
            # it — same transaction, no change to the delete's condition,
            # timing, or the transaction boundary itself.
            await conn.execute(
                """
                INSERT INTO flag_ack_history (
                    flag_id, watchlist_id, severity_rank_at_ack, z_score_at_ack, acked_at, superseded_at
                )
                SELECT flag_id, watchlist_id, severity_rank_at_ack, z_score_at_ack, acked_at, now()
                FROM flag_ack WHERE flag_id = $1
                """,
                flag_id,
            )
            await conn.execute("DELETE FROM flag_ack WHERE flag_id = $1", flag_id)
            ack_busted = True
        # Equal rank and de-escalation (new_rank <= previous_rank) both fall
        # through here doing nothing — flag_ack stays, per the asymmetric
        # design in DATA_MODEL.md.

        return UpsertResult(id=flag_id, severity_rank=new_rank, was_insert=was_insert, ack_busted=ack_busted)
