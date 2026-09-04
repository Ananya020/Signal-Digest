"""HistoricalReplayProvider — replays real historical price_ticks chronologically.

Phase 1 scope: no NSE trading-hours modeling, no scheduler. A `ReplayClock`
exposes a single explicit `advance()` step so replay is deterministic and
testable without wall-clock sleeps. Every tick emitted by this provider is
real historical data (loaded from `price_ticks` where source='real_historical')
re-tagged `source='replay_simulated'` — never randomly generated.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

import asyncpg

from app.providers.base import ProviderStatus, Tick


@dataclass
class PricePoint:
    ts: datetime
    price: float
    volume: int


class ReplayClock:
    """Explicit step counter. Injected so tests can drive replay deterministically."""

    def __init__(self, start_step: int = 0) -> None:
        self._step = start_step

    def current(self) -> int:
        return self._step

    def advance(self) -> int:
        self._step += 1
        return self._step

    def reset(self, step: int = 0) -> None:
        self._step = step


@dataclass
class HistoricalReplayProvider:
    """Implements MarketDataProvider by walking pre-loaded historical series.

    `history`: ticker -> chronologically sorted list of PricePoint, one per
    trading day. All tickers advance in lockstep on a single shared step index
    (index 0 = each ticker's earliest loaded observation).
    """

    history: dict[str, list[PricePoint]]
    clock: ReplayClock = field(default_factory=ReplayClock)

    def get_ticks(self, tickers: list[str]) -> list[Tick]:
        step = self.clock.current()
        ticks: list[Tick] = []
        for ticker in tickers:
            series = self.history.get(ticker, [])
            if step >= len(series):
                continue  # this ticker's history is exhausted at the current step
            point = series[step]
            ticks.append(
                Tick(
                    ticker=ticker,
                    price=point.price,
                    volume=point.volume,
                    timestamp=point.ts,
                    source="replay_simulated",
                )
            )
        return ticks

    def advance(self) -> int:
        return self.clock.advance()

    def get_previous_price(self, ticker: str) -> float | None:
        """The close immediately preceding the current replay step — used by
        the scoring pipeline (Phase 4) to compute today's return without
        reaching into `history` directly, so it works the same way whether
        called on this provider or through FaultInjectingProvider's
        delegation. None if there's no prior day (step 0) or no data."""
        step = self.clock.current()
        series = self.history.get(ticker, [])
        if step == 0 or step - 1 >= len(series):
            return None
        return series[step - 1].price

    def get_status(self) -> ProviderStatus:
        step = self.clock.current()
        max_len = max((len(s) for s in self.history.values()), default=0)
        exhausted = step >= max_len
        now = datetime.now(timezone.utc)
        return ProviderStatus(
            state="UNAVAILABLE" if exhausted else "LIVE",
            last_successful_fetch=now,
            age_seconds=0.0,
            detail=(
                f"replay exhausted at step {step}/{max_len}"
                if exhausted
                else f"replay step {step}/{max_len}"
            ),
        )


async def load_history(pool: asyncpg.Pool, tickers: list[str]) -> dict[str, list[PricePoint]]:
    """Loads real_historical price_ticks for the given tickers, chronologically sorted."""
    rows = await pool.fetch(
        """
        SELECT ticker, ts, price, volume
        FROM price_ticks
        WHERE source = 'real_historical' AND ticker = ANY($1::text[])
        ORDER BY ticker, ts ASC
        """,
        tickers,
    )
    history: dict[str, list[PricePoint]] = {ticker: [] for ticker in tickers}
    for row in rows:
        history[row["ticker"]].append(
            PricePoint(ts=row["ts"], price=float(row["price"]), volume=row["volume"])
        )
    return history
