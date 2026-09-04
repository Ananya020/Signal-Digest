"""Digest state and the aggregate ETag hash.

Modeled on Groww's "Improving the Efficiency of Rendering User Holdings"
ETag pattern (PRODUCT.md) — the aggregate hash is a fingerprint of the
watchlist's CURRENT UNACKNOWLEDGED FLAG SET, computed fresh from committed
DB state on every request, never cached/trusted from the client.

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
_UNACKED_FLAGS_SQL = """
    SELECT f.id, f.ticker, f.trading_day, f.signal_type, f.z_score,
           f.severity, f.severity_rank, f.volume_ratio, f.sector_relative,
           f.computed_at, f.provider_state_at_computation
    FROM flags f
    JOIN watchlist_items wi ON wi.ticker = f.ticker
    LEFT JOIN flag_ack fa ON fa.flag_id = f.id AND fa.watchlist_id = wi.watchlist_id
    WHERE wi.watchlist_id = $1 AND fa.flag_id IS NULL
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
