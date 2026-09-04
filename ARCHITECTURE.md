# Architecture

## System diagram
```
Next.js Frontend (Dashboard / Digest / Detail / "show your work" chart / fault-injection demo toggle)
        │ HTTPS JSON
        ▼
FastAPI Backend — single modular monolith (not microservices; see CLAUDE.md for why)
  ├─ API layer (routers) + simple JWT auth (single demo account, no multi-tenant RBAC)
  │    Phase 3: JWT not yet implemented — `app/auth.py::get_current_user()` is the single
  │    seam standing in for it (always returns one hardcoded demo user UUID). Every
  │    watchlist endpoint resolves identity only through this dependency and still
  │    enforces `watchlist.user_id` ownership (`app/services/watchlist_access.py`), so
  │    swapping in real JWT later touches only this one function's body.
  ├─ Digest Service — fetch flags, compute/verify state hash (ETag), ack handling (after-commit only)
  ├─ Scoring Engine — z-score, volume ratio, sector tag, severity band
  ├─ Data Provider Abstraction (below) — real provider, mock/replay, fault injector
  └─ Background Scheduler (APScheduler) — periodic tick ingestion, baseline recompute, flag generation
        │
        ▼
PostgreSQL — see DATA_MODEL.md

Cross-cutting: structured logging (every flag decision logged with inputs — audit/demo trail),
/health + /metrics (freshness state, ETag hit-rate), Pydantic input validation, CORS locked to
frontend origin, secrets via env vars only.
```

## Data provider abstraction
Normalized internal model, provider-agnostic:

```python
class Tick(BaseModel):
    ticker: str
    price: float
    volume: int
    timestamp: datetime
    source: Literal["real_historical", "replay_simulated", "fault_injected"]

class ProviderStatus(BaseModel):
    state: Literal["LIVE", "RECENT", "DELAYED", "STALE", "UNAVAILABLE"]
    last_successful_fetch: datetime
    age_seconds: float
    detail: str
```

**Freshness thresholds — configurable, demo-compressed (Phase 4):** all four boundaries are env vars read by `app/services/freshness.py`, no hardcoded values anywhere in freshness-state code.

| Env var | Demo default | Original (production-scale) figure |
|---|---|---|
| `FRESHNESS_LIVE_SECONDS` | 5 | 15 |
| `FRESHNESS_RECENT_SECONDS` | 15 | 120 (2min) |
| `FRESHNESS_DELAYED_SECONDS` | 30 | 600 (10min) |
| `FRESHNESS_STALE_SECONDS` | 30 | 600 (10min) |

A production deployment against real intraday/EOD equity data would reasonably use the original minutes-scale figures — they're shortened here specifically so live fault-injection (outage/stale/recover) is demonstrable within a 5-minute presentation instead of requiring a 10+ minute real wait. UNAVAILABLE = provider call failing / kill-switch engaged (last-known values shown, explicit banner, no new flags computed) — this state overrides the threshold table entirely, regardless of `age_seconds`.

**Interface:**
```python
class MarketDataProvider(Protocol):
    def get_ticks(self, tickers: list[str]) -> list[Tick]: ...
    def get_status(self) -> ProviderStatus: ...
```

**Implementations:**
1. `HistoricalReplayProvider` — real yfinance OHLCV for ~30-50 NSE stocks, replayed/perturbed on a clock tick. Default and only provider — disclosed simulation.
   - Phase 1 implementation (`backend/app/providers/historical_replay.py`): a `ReplayClock` holds a single explicit step index, injected rather than wall-clock-driven, so replay is deterministic and testable. All tickers advance in lockstep on that one shared index. `get_ticks()` returns each requested ticker's historical observation at the current step, re-tagged `source="replay_simulated"` — the underlying price/volume values are always real historical data loaded from `price_ticks` (`source="real_historical"`), never randomly generated. No NSE trading-hours modeling yet; that's a later phase.
2. `FaultInjectingProvider` — **decorator around #1**, not a separate path. Phase 4 implementation (`backend/app/providers/fault_injecting.py`), wrapped once at app startup:
   - `outage` → `get_ticks()` raises `ProviderUnavailableError` / `get_status()` → `UNAVAILABLE` immediately, regardless of `age_seconds` — a harder failure than staleness, not a slower version of it.
   - `stale` → freezes the wrapped provider's replay position (`advance()` no-ops); does **not** touch `age_seconds`, which is always real wall-clock time since `last_successful_fetch` and grows naturally past the configured thresholds purely because real time passes while the replay position doesn't move.
   - `recover` → not a stored mode itself, transitions back to `normal`; the *next* scheduler tick resumes from wherever the replay position was left (not recalculated from wall-clock time) and scores it for real — freshness does not snap back to LIVE at the moment of recovery, only once that next tick's `get_ticks()` call actually refreshes `last_successful_fetch`.
   - `provider_state` (mode, frozen_at, **and `last_successful_fetch`**) persists across a process restart — corrected after an empirically-verified bug: freshness depends only on `age = now - last_successful_fetch`, so an earlier version that persisted just mode/frozen_at let a restart during a genuine `stale` fault report `LIVE` immediately after (see PROGRESS.md). All three fields now persist together via `FaultInjectingProvider.persist()`, called on every fault change and every scheduler tick. Concurrent `/admin/fault` calls are last-write-wins, a single UPSERT on the fixed `id=1` row, no locking.

This exercises the exact same code path a real outage would hit — that's what makes the live demo defensible under "is that faked?" scrutiny. Verified live end-to-end (see PROGRESS.md) with a scheduler-driven severity-escalation-flip; note the architectural finding there that genuine same-key escalation requires a constructed precondition under this project's daily-close (not intraday) replay granularity.

## API design

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/watchlists` | list current demo user's watchlists | Phase 5 implemented (`app/routers/watchlists.py`). Ownership-scoped via `WHERE user_id = $1` — same pattern as every other watchlist endpoint. |
| POST | `/watchlists` | create watchlist | |
| POST | `/watchlists/{id}/items` | add ticker | idempotent upsert on PK |
| DELETE | `/watchlists/{id}/items/{ticker}` | remove ticker | |
| GET | `/tickers` | list the fixed ticker universe | Phase 5 implemented (`app/routers/tickers.py`). `{ticker, name, sector}[]`. Universe metadata, not user data — no auth scoping. |
| GET | `/watchlists/{id}/digest` | current flags + freshness state | Returns `ETag` header = aggregate hash; client sends `If-None-Match` → 304 if unchanged. Phase 3 implemented, Phase 4 wired real freshness — `freshness` field reflects the live `ProviderStatus.state` (`app/routers/watchlists.py`), no longer hardcoded. When `UNAVAILABLE`, still returns the last-known unacked flags (never empties the response) with `detail` making clear no new scoring occurred. |
| POST | `/watchlists/{id}/ack` | ack specific flag IDs | `{flag_ids: [...]}` — no client-supplied hash accepted; server always recomputes authoritative hash, never trusts client's. Phase 3 implemented; `ignored` entries are `{id, reason}` objects (Phase 3 correction). |
| GET | `/tickers/{ticker}/evidence?flag_id=` | "show your work" data | `{ticker, window_start, window_end, mean_return, stdev_return, points: [{date, return, price}], flagged_point: {date, return, z_score}}` — frontend draws directly, no client-side stats recomputation. Phase 3 implemented (`app/services/evidence.py`); `mean_return`/`stdev_return`/`points` come from the exact same baseline row (`load_latest_baseline`) that produced the flag's stored `z_score` — not independently recomputed — so the displayed band and the displayed z_score are always algebraically consistent (reproducible within floating-point tolerance, tested). The flagged day's own return is fetched separately and may fall outside the plotted `points` window, since the baseline is static (Phase 2). |
| GET | `/provider/status` | current freshness state | Phase 4 implemented (`app/routers/provider_status.py`). `age_seconds` computed live from real wall-clock time on every call, never cached. Polled every 3s for the freshness banner (Phase 5). Phase 5 added `demo_mode: bool` (same flag `/admin/fault` is gated behind) so the frontend knows whether to render the fault-injection control without guessing/hardcoding. |
| POST | `/admin/fault` | demo-only fault injection | Phase 4 implemented (`app/routers/admin.py`). `{"mode": "outage"\|"stale"\|"recover"}`. Gated behind `DEMO_MODE` at the route level — 404 unconditionally if unset, checked before touching the provider or DB. Updates `provider_state`, last-write-wins (no locking). |
| GET | `/metrics` | ETag short-circuit rate (stretch) | |

**Minimal live scheduler (Phase 4, `app/main.py` lifespan):** one `AsyncIOScheduler` job, one configurable interval (`SCHEDULER_INTERVAL_SECONDS`, default 5s), started/stopped with the app lifecycle. Calls `app/services/scoring_pipeline.py::run_scoring_cycle()` — the exact per-tick logic extracted from Phase 2's manual script, so the script and the live scheduler can never drift apart — then unconditionally calls `provider.advance()` (a no-op internally whenever fault-frozen, so the scheduler itself never branches on fault state). Not a general-purpose job framework — one job, nothing more.

**Idempotency:** `POST /items` upserts on composite PK. `POST /ack` uses `ON CONFLICT DO NOTHING` — safe to replay, which is what makes refresh-mid-ack and duplicate requests safe by construction.

## Frontend (Phase 5)

Next.js App Router, `"use client"` throughout (no server components needed at this scale) — `frontend/app/page.tsx` is the entire dashboard. Client-side state is deliberately split into: a pure ETag-poll reducer (`lib/digestPoll.ts`, 304 leaves state untouched by reference, 200 updates it), independent 3s (`useProviderStatus`) and 5s (`useDigest`, matching the backend's default scheduler cadence) polling hooks, and a `viewed` vs. `latest` distinction in `page.tsx` so a background poll never silently rewrites what the user is looking at — new flags surface as a pull-in affordance instead. Ack has a 1.5s dwell delay (`lib/dwell.ts`) before the ack control is even clickable, per the Stage 2 UX design. The evidence chart is hand-rolled inline SVG (`components/EvidencePanel.tsx`) — no charting library. Severity/freshness badges always render color+icon+text together through one shared `Badge` component, enforced structurally (tested) rather than by convention. Bootstrap watchlist creation (`lib/bootstrap.ts`) always checks `GET /watchlists` first and only creates+seeds on an empty result — verified live to never duplicate across reloads.

**Aggregate ETag hash (locked scheme, `app/services/digest.py`):** for every unacknowledged flag belonging to the watchlist's tickers, take `(flag_id, severity_rank)`; sort by `flag_id` ascending; serialize as `json.dumps([[flag_id, severity_rank], ...], separators=(',', ':'))`; SHA-256 hex digest of the UTF-8 bytes. Independently reproducible from this description alone. Always computed fresh from committed DB state on every request — never cached, never trusts a client-supplied hash.

**Optional LLM explanation layer, if built:** `POST /internal/phrase` takes `{z_score, volume_ratio, sector_relative}`, returns a one-line string. Pure post-processing — never touches `flags` decision logic, trivially swappable for the deterministic template fallback.

## Folder structure
```
signalDigest/
├── docker-compose.yml       # Postgres only — backend/frontend run locally, not containerized
├── .env.example
├── backend/
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── migrations/
│   │   ├── 001_init.sql     # numbered SQL files applied manually via `psql -f`, no migration tool for this build
│   │   └── 002_add_last_successful_fetch.sql  # Phase 4 correction: persist provider_state.last_successful_fetch
│   ├── scripts/
│   │   ├── seed_historical_data.py   # one-off manual backfill: yfinance -> tickers/price_ticks -> baselines
│   │   ├── smoke_test_replay.py      # one-off manual check: replay real seeded data, confirm source='replay_simulated'
│   │   ├── run_scoring_once.py       # manual scoring trigger; calls the same run_scoring_cycle the live scheduler uses
│   │   ├── seed_demo_escalation_precondition.py  # Phase 4: manual-only, seeds a constructed low-severity+ack
│   │   │                                precondition for a real not-yet-reached day, for the live escalation-flip demo beat
│   │   └── reset_demo_state.py       # Phase 5: truncates flags/flag_ack/watchlist_ack_state, resets provider_state;
│   │                                    leaves real seeded data and user watchlists untouched
│   ├── tests/                # pytest + pytest-asyncio; DB-backed tests run against real local Postgres
│   └── app/
│       ├── main.py          # FastAPI app + CORS + lifespan (DB pool, provider construction, APScheduler job — Phase 4)
│       ├── config.py        # pydantic-settings, reads .env (incl. freshness thresholds, scheduler interval — Phase 4)
│       ├── db.py            # asyncpg pool
│       ├── auth.py          # demo-user identity seam (get_current_user, DEMO_USER_ID)
│       ├── schemas.py       # Pydantic request bodies (WatchlistCreate, AckRequest, ...)
│       ├── data/
│       │   ├── tickers.py   # fixed TICKER_SECTORS universe + to_nse_symbol()
│       │   └── baselines.py # rolling-window baseline computation
│       ├── providers/
│       │   ├── base.py               # Tick, ProviderStatus, MarketDataProvider protocol
│       │   ├── historical_replay.py  # HistoricalReplayProvider + ReplayClock (+get_previous_price, Phase 4)
│       │   └── fault_injecting.py    # FaultInjectingProvider decorator (Phase 4)
│       ├── services/
│       │   ├── scoring.py            # deterministic scoring engine (Phase 2)
│       │   ├── flags.py              # severity-escalation ack-bust upsert (Phase 2)
│       │   ├── digest.py             # aggregate ETag hash + unacked-flags query (Phase 3)
│       │   ├── watchlist_access.py   # ownership check (Phase 3)
│       │   ├── evidence.py           # "show your work" evidence builder (Phase 3)
│       │   ├── scoring_pipeline.py   # run_scoring_cycle — shared by script and scheduler (Phase 4)
│       │   ├── freshness.py          # classify_freshness, configurable thresholds (Phase 4)
│       │   └── provider_state.py     # provider_state table persistence (Phase 4)
│       └── routers/
│           ├── health.py           # GET /health (real SELECT 1)
│           ├── watchlists.py       # GET/POST /watchlists, /items, GET /digest, POST /ack
│           ├── tickers.py          # GET /tickers, GET /tickers/{ticker}/evidence
│           ├── admin.py            # POST /admin/fault, DEMO_MODE-gated (Phase 4)
│           └── provider_status.py  # GET /provider/status (Phase 4, +demo_mode in Phase 5)
└── frontend/                # Next.js (App Router) + Tailwind
    ├── vitest.config.mts / vitest.setup.ts   # component + unit test tooling (Phase 5)
    ├── app/
    │   ├── page.tsx          # the entire dashboard — bootstrap, digest, banner, fault control, evidence panel
    │   └── layout.tsx
    ├── components/
    │   ├── Badge.tsx              # shared color+icon+text renderer (accessibility invariant lives here)
    │   ├── SeverityBadge.tsx / FreshnessBanner.tsx
    │   ├── FaultControl.tsx       # only rendered when /provider/status.demo_mode is true
    │   ├── DigestList.tsx / DigestRow.tsx / SkeletonRows.tsx
    │   └── EvidencePanel.tsx      # hand-rolled inline SVG chart, no charting library
    ├── hooks/
    │   ├── useProviderStatus.ts   # 3s poll
    │   └── useDigest.ts           # 5s poll, ETag-aware
    └── lib/
        ├── api.ts, types.ts       # typed fetch client matching the real backend contracts
        ├── digestPoll.ts          # pure 304/200 reducer (tested)
        ├── dwell.ts               # ack dwell-delay timer (tested)
        ├── severity.ts            # badge config (tested for the accessibility invariant)
        ├── explain.ts             # deterministic one-line flag explanation, no LLM
        └── bootstrap.ts           # idempotent first-run watchlist creation (tested)
```
