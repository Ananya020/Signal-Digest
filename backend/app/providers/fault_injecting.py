"""FaultInjectingProvider — decorator around HistoricalReplayProvider, per
ARCHITECTURE.md's design (not a separate/parallel provider implementation).
Implements the same shape as MarketDataProvider (plus `advance()` and
`get_previous_price()`, the two extra methods Phase 2/4's scoring pipeline
needs); delegates to the wrapped provider except when a fault mode is
active. One instance, wrapped once at app startup — the scheduler and every
other consumer are unaware whether they're talking to a plain or
fault-wrapped provider.

## Freeze semantics (locked, Phase 4)

- **'stale'**: the wrapped provider's replay position does NOT advance
  (`advance()` no-ops). `get_ticks()` still returns the same frozen tick as
  "last known" data, but does NOT refresh `last_successful_fetch` — so
  `age_seconds` (always real wall-clock time since `last_successful_fetch`)
  grows naturally and crosses the configured freshness thresholds purely
  because real time passes while the replay position doesn't move. This is
  what makes STALE "real, not a fake label."
- **'outage'**: a harder failure, not a slower staleness. `get_ticks()`
  raises `ProviderUnavailableError`; `get_status()` reports `UNAVAILABLE`
  immediately, regardless of `age_seconds`.
- **'normal'**: fully delegates. `last_successful_fetch` refreshes on every
  `get_ticks()` call; the replay position advances normally.
- 'recover' is not a stored mode itself (see app/services/provider_state.py)
  — it transitions `mode` back to `'normal'`. Freshness does NOT snap back
  to LIVE at the moment of recovery; it stays whatever real elapsed time
  since the last genuine fetch dictates, until the next successful
  `get_ticks()` call refreshes `last_successful_fetch`. This matches the
  demo sequence's expectation of waiting for the next scheduler tick to
  fire naturally, rather than forcing it.

## provider_state persistence — corrected (Phase 4, post-verification)

`mode`, `frozen_at`, AND `last_successful_fetch` are all read from / written
to the `provider_state` table. The original Phase 4 implementation did not
persist `last_successful_fetch`, reasoning it was a narrow, documented
limitation ("a restart resets the freshness age clock, but mode is
correctly restored"). That was verified WRONG with a simulated restart:
freshness classification depends entirely on `age = now - last_successful_fetch`
— `frozen_at` never enters that computation, it's cosmetic (only used in
`detail`). So a restart during a genuine `'stale'` fault reset
`last_successful_fetch` to the restart moment, and `get_status()`
immediately reported LIVE despite the feed having been genuinely stale for
real minutes beforehand — a correctness bug, not a narrow limitation
('outage' was unaffected, since its UNAVAILABLE branch never consults
`age_seconds` at all).

Fix: `last_successful_fetch` now persists via the same atomic UPSERT as
`mode`/`frozen_at` (`app/services/provider_state.py`) —
- `sync_from_db()` hydrates all three at startup.
- `persist()` writes all three; called by `/admin/fault` on every mode
  change and by the scheduler on every tick (so an unclean crash during
  `'normal'` operation loses at most one scheduler interval of freshness
  precision, not the whole restart's worth).

## replay_step persistence — second instance of the same bug class

Found on the real deployed instance (Render free tier spin-down/wake), not
in local testing: `HistoricalReplayProvider`'s `ReplayClock` was
process-memory only. A restart reset it to step 0, so the scheduler
silently re-walked history from day one — no new flags scored for ~20+
ticks while `sample_size` re-climbed past the confidence gate — even though
previously-computed flags remained correctly stored in Postgres. Exactly
the same shape as the `last_successful_fetch` bug above: an in-memory value
that must survive a restart wasn't being persisted.

Fix, same pattern: `replay_step` (`004_persist_replay_step.sql`) now
persists via the same UPSERT.
- `sync_from_db()` additionally resets `wrapped.clock` to the persisted
  step, when one exists.
- `persist()` additionally writes `wrapped.clock.current()`.
- Freeze semantics are unchanged: `'stale'` still no-ops `advance()`, so a
  frozen clock simply persists the same frozen value tick after tick — this
  fix only changes what happens at startup, not the freeze/recover
  mechanism itself.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

import asyncpg

from app.providers.base import ProviderStatus, Tick
from app.providers.historical_replay import HistoricalReplayProvider
from app.services.freshness import classify_freshness
from app.services.provider_state import save_provider_state

FaultMode = Literal["normal", "outage", "stale"]


class ProviderUnavailableError(Exception):
    """Raised by get_ticks() during an injected outage."""


@dataclass
class FaultInjectingProvider:
    wrapped: HistoricalReplayProvider
    live_seconds: float
    recent_seconds: float
    delayed_seconds: float
    stale_seconds: float
    mode: FaultMode = "normal"
    frozen_at: datetime | None = None
    last_successful_fetch: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_ticks(self, tickers: list[str]) -> list[Tick]:
        if self.mode == "outage":
            raise ProviderUnavailableError("provider is in injected outage mode")
        ticks = self.wrapped.get_ticks(tickers)
        if self.mode == "normal":
            self.last_successful_fetch = datetime.now(timezone.utc)
        # mode == "stale": return the same frozen-position ticks, but do
        # NOT refresh last_successful_fetch — no new fetch actually happened.
        return ticks

    def advance(self) -> int:
        if self.mode == "normal":
            return self.wrapped.advance()
        return self.wrapped.clock.current()  # frozen: no-op, by design

    def get_previous_price(self, ticker: str) -> float | None:
        return self.wrapped.get_previous_price(ticker)

    def get_status(self) -> ProviderStatus:
        now = datetime.now(timezone.utc)
        age = (now - self.last_successful_fetch).total_seconds()

        if self.mode == "outage":
            return ProviderStatus(
                state="UNAVAILABLE",
                last_successful_fetch=self.last_successful_fetch,
                age_seconds=age,
                detail=(
                    f"outage: fault-injected since {self.frozen_at.isoformat()}"
                    if self.frozen_at else "outage: fault-injected"
                ),
            )

        state = classify_freshness(age, self.live_seconds, self.recent_seconds, self.delayed_seconds, self.stale_seconds)
        detail = f"mode={self.mode}, replay step {self.wrapped.clock.current()}"
        if self.mode == "stale" and self.frozen_at is not None:
            detail += f", frozen at {self.frozen_at.isoformat()}"
        return ProviderStatus(state=state, last_successful_fetch=self.last_successful_fetch, age_seconds=age, detail=detail)

    def set_mode(self, mode: FaultMode) -> None:
        self.mode = mode
        self.frozen_at = datetime.now(timezone.utc) if mode in ("outage", "stale") else None

    async def sync_from_db(self, pool: asyncpg.Pool) -> None:
        """Hydrates `mode`/`frozen_at`/`last_successful_fetch`/replay step
        from the persisted provider_state row — called once at startup so
        fault mode, freshness age, AND replay position correctly survive a
        process restart."""
        row = await pool.fetchrow(
            "SELECT mode, frozen_at, last_successful_fetch, replay_step FROM provider_state WHERE id = 1"
        )
        if row is None:
            return
        db_mode = row["mode"]
        self.mode = db_mode if db_mode in ("outage", "stale") else "normal"
        self.frozen_at = row["frozen_at"]
        if row["last_successful_fetch"] is not None:
            self.last_successful_fetch = row["last_successful_fetch"]
        # else: no persisted value yet (very first startup) — keep the
        # in-memory default (now()).
        if row["replay_step"] is not None:
            self.wrapped.clock.reset(row["replay_step"])
        # else: no persisted step yet (very first startup) — keep whatever
        # start_step the caller constructed `wrapped.clock` with.

    async def persist(self, pool: asyncpg.Pool) -> None:
        """Writes current mode/frozen_at/last_successful_fetch/replay step to
        provider_state. Called on every /admin/fault change and on every
        scheduler tick, so a restart's freshness-age precision loss AND
        replay-position loss are both bounded by one scheduler interval, not
        unbounded."""
        await save_provider_state(
            pool, self.mode, self.frozen_at, self.last_successful_fetch,
            self.wrapped.clock.current(),
        )
