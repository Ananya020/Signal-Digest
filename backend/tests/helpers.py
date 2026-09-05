from datetime import date, datetime, timezone


async def insert_flag(
    db_pool,
    ticker: str,
    trading_day: date,
    severity_rank: int = 1,
    severity: str = "notable",
    signal_type: str = "price_zscore",
    z_score: float = 2.1,
    sector_relative: str | None = None,
) -> int:
    """Directly inserts a flag row for API-level test setup. Phase 2's
    scoring pipeline is tested separately (test_scoring.py, test_flags_ack_bust.py);
    Phase 3 tests only need arbitrary, valid flag rows to exercise the
    digest/ack/evidence endpoints against."""
    row = await db_pool.fetchrow(
        """
        INSERT INTO flags (
            ticker, trading_day, signal_type, z_score, severity, severity_rank,
            volume_ratio, sector_relative, computed_at, provider_state_at_computation
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """,
        ticker, trading_day, signal_type, z_score, severity, severity_rank,
        1.5, sector_relative, datetime.now(timezone.utc), "replay_simulated",
    )
    return row["id"]
