"""One scoring cycle — extracted from Phase 2's run_scoring_once.py so both
the manual script and Phase 4's scheduler invoke the exact same logic,
never duplicated.

Freshness gating (RELIABILITY.md #1 — "scoring off nothing without gating
it"): if the provider reports UNAVAILABLE, this cycle is skipped entirely,
no DB writes. If the provider is frozen (fault mode 'stale'), the same tick
keeps being re-evaluated every cycle; Phase 2's ack-bust upsert already
handles "same severity -> refresh evidence, no ack-bust" correctly under
repeated identical input (verified by a dedicated Phase 4 regression test)
— no special-casing needed here for that.
"""

from datetime import datetime, timezone

import asyncpg

from app.data.baselines import compute_baseline_as_of, load_price_series, upsert_baseline
from app.data.tickers import TICKER_SECTORS, to_nse_symbol
from app.services.flags import upsert_flag_with_ack_bust
from app.services.scoring import (
    compute_return,
    score_price_zscore,
    score_volatility_regime,
    trading_day_from_tick,
)

SECTOR_BY_NSE_TICKER = {to_nse_symbol(bare): sector for bare, sector in TICKER_SECTORS.items()}
ALL_TICKERS = list(SECTOR_BY_NSE_TICKER.keys())


async def run_scoring_cycle(pool: asyncpg.Pool, provider, tickers: list[str], sector_by_ticker: dict[str, str]) -> dict:
    """Runs one scoring cycle against whatever `provider.get_ticks()`
    currently reports. `provider` may be a plain HistoricalReplayProvider or
    a FaultInjectingProvider — both implement get_status()/get_ticks()/
    get_previous_price() identically from this function's point of view.

    Does NOT call provider.advance() — the caller (script or scheduler)
    controls when replay position moves, since that's a policy decision
    (e.g. the scheduler always calls it; a fault-frozen provider makes it a
    no-op internally either way)."""
    status = provider.get_status()
    if status.state == "UNAVAILABLE":
        return {"scored": False, "reason": "UNAVAILABLE", "flags": [], "provider_state": status.state}

    try:
        ticks = provider.get_ticks(tickers)
    except Exception as e:  # noqa: BLE001 — provider-level failure, must not crash the caller
        return {"scored": False, "reason": f"get_ticks_error: {e}", "flags": [], "provider_state": status.state}

    if not ticks:
        return {"scored": False, "reason": "no_ticks", "flags": [], "provider_state": status.state}

    today_returns: dict[str, float] = {}
    for tick in ticks:
        prev_price = provider.get_previous_price(tick.ticker)
        if prev_price is None:
            continue  # no prior close to compute a return from yet
        today_returns[tick.ticker] = compute_return(prev_price, tick.price)

    flags: list[dict] = []
    async with pool.acquire() as conn:
        for tick in ticks:
            if tick.ticker not in today_returns:
                continue

            trading_day = trading_day_from_tick(tick)

            # Rolling baseline, recomputed fresh this cycle from only the
            # days strictly before trading_day — look-ahead-safe (Workstream
            # 1, see PROGRESS.md). Persisted as a new (ticker, as_of_date)
            # row, never overwriting an earlier day's row.
            series = await load_price_series(pool, tick.ticker)
            baseline = compute_baseline_as_of(tick.ticker, series, trading_day)
            if baseline is None:
                continue
            await upsert_baseline(pool, baseline)

            sector = sector_by_ticker.get(tick.ticker)
            peer_returns = [
                r for t, r in today_returns.items()
                if t != tick.ticker and sector_by_ticker.get(t) == sector
            ]

            candidates = []
            price_flag = score_price_zscore(
                ticker=tick.ticker,
                trading_day=trading_day,
                today_return=today_returns[tick.ticker],
                today_volume=tick.volume,
                baseline=baseline,
                peer_returns=peer_returns,
                computed_at=datetime.now(timezone.utc),
                provider_state=tick.source,
            )
            if price_flag:
                candidates.append(price_flag)

            vol_flag = score_volatility_regime(
                ticker=tick.ticker,
                trading_day=trading_day,
                baseline=baseline,
                computed_at=datetime.now(timezone.utc),
                provider_state=tick.source,
            )
            if vol_flag:
                candidates.append(vol_flag)

            for candidate in candidates:
                result = await upsert_flag_with_ack_bust(conn, candidate)
                flags.append({
                    "id": result.id,
                    "ticker": candidate.ticker,
                    "signal_type": candidate.signal_type,
                    "severity": candidate.severity,
                    "z_score": candidate.z_score,
                    "was_insert": result.was_insert,
                    "ack_busted": result.ack_busted,
                })

    return {"scored": True, "reason": None, "flags": flags, "provider_state": status.state}
