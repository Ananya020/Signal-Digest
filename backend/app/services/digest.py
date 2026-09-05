"""Digest state and the aggregate ETag hash.

Modeled on Groww's "Improving the Efficiency of Rendering User Holdings"
ETag pattern (PRODUCT.md) — the aggregate hash is a fingerprint of the
watchlist's CURRENT UNACKNOWLEDGED FLAG SET, computed fresh from committed
DB state on every request, never cached/trusted from the client.

As of the one-flag-per-ticker digest decision below, "flag set" means the
rows _UNACKED_FLAGS_SQL actually surfaces (at most one unacked flag per
ticker) — not every unacknowledged row in `flags`. An older, suppressed
flag for a ticker that already has a shown flag can't change the hash or
trigger a "new signals" notification, which is correct: nothing new is
visible to the user until it either gets acknowledged (promoting the next
one) or is superseded by a more severe flag.

## Canonical hash scheme (locked, do not invent an alternative)

For every currently unacknowledged flag belonging to one of the watchlist's
tickers: include `(flag_id, severity_rank)`. Sort by `flag_id` ascending.
Serialize as `json.dumps([[flag_id, severity_rank], ...], separators=(',', ':'))`
— a JSON array of two-element integer arrays, no whitespace. Hash the
UTF-8-encoded bytes with SHA-256, hex digest.

This exact scheme is documented here so a hash can be independently
reproduced by a future consumer without re-deriving it from this codebase.
"""

import hashlib
import json

import asyncpg

EMPTY_DIGEST_SERIALIZED = "[]"
EMPTY_DIGEST_HASH = hashlib.sha256(EMPTY_DIGEST_SERIALIZED.encode("utf-8")).hexdigest()

# Reuses the exact join shape from DATA_MODEL.md's "what's changed since
# last check" key query — flags for the watchlist's tickers with no
# corresponding flag_ack row for this watchlist.
#
# `signal_type = 'price_zscore'` filter: a deliberate product decision, not
# a bug fix (see PRODUCT.md's "volatility_regime is computed but not
# surfaced" note). volatility_regime flags are still computed and persisted
# by the scoring engine exactly as before — this filter only affects what
# GET /digest returns; no rows are deleted or the computation skipped.
#
# One row per ticker, not one row per unacked flag: a ticker can accumulate
# many real, distinct-trading-day unacknowledged flags over time (verified
# against real data — not a duplicate-day bug), and the digest's job is
# "what needs your attention right now", not a full backlog. DISTINCT ON
# (f.ticker) keeps only the single most-severe unacked flag per ticker
# (ties broken by |z_score|, then most recent trading_day). Every
# unacknowledged flag still exists in `flags` and is unaffected by this
# query — nothing is deleted or auto-acked, and the full history remains
# reachable via GET /tickers/{ticker}/flags regardless of digest visibility.
# The severity-escalation ack-bust rule in flags.py operates on individual
# flag rows keyed by (ticker, trading_day, signal_type), entirely
# independent of which rows this query happens to surface, so suppressing
# older same-ticker flags here has no effect on that rule for the flag that
# IS shown.
#
# `ORDER BY abs(z_score) DESC`: the digest is ranked by statistical
# unusualness, most extreme first — explicit now that price_zscore is the
# only signal_type shown, since z_score is always non-NULL for it.
_UNACKED_FLAGS_SQL = """
    SELECT id, ticker, trading_day, signal_type, z_score, severity,
           severity_rank, volume_ratio, sector_relative, computed_at,
           provider_state_at_computation, sector
    FROM (
        SELECT DISTINCT ON (f.ticker)
               f.id, f.ticker, f.trading_day, f.signal_type, f.z_score,
               f.severity, f.severity_rank, f.volume_ratio, f.sector_relative,
               f.computed_at, f.provider_state_at_computation, t.sector
        FROM flags f
        JOIN watchlist_items wi ON wi.ticker = f.ticker
        JOIN tickers t ON t.ticker = f.ticker
        LEFT JOIN flag_ack fa ON fa.flag_id = f.id AND fa.watchlist_id = wi.watchlist_id
        WHERE wi.watchlist_id = $1 AND fa.flag_id IS NULL AND f.signal_type = 'price_zscore'
        ORDER BY f.ticker, f.severity_rank DESC, abs(f.z_score) DESC, f.trading_day DESC
    ) most_severe_per_ticker
    ORDER BY abs(z_score) DESC
"""


def compute_aggregate_hash(pairs: list[tuple[int, int]]) -> str:
    """`pairs` need not be pre-sorted or deduplicated by the caller — sorting
    happens here so the hash is reproducible regardless of DB/query
    iteration order."""
    sorted_pairs = sorted((int(flag_id), int(severity_rank)) for flag_id, severity_rank in pairs)
    serialized = json.dumps([list(p) for p in sorted_pairs], separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def load_unacked_flags(pool: asyncpg.Pool, watchlist_id) -> list[asyncpg.Record]:
    """Authoritative current DB state — always re-queried, never cached."""
    return await pool.fetch(_UNACKED_FLAGS_SQL, watchlist_id)


async def compute_digest(pool: asyncpg.Pool, watchlist_id) -> tuple[str, list[asyncpg.Record]]:
    """Returns (aggregate_hash, unacked_flag_rows)."""
    rows = await load_unacked_flags(pool, watchlist_id)
    pairs = [(row["id"], row["severity_rank"]) for row in rows]
    return compute_aggregate_hash(pairs), rows
