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

**Freshness thresholds:** LIVE <15s · RECENT 15s-2min · DELAYED 2-10min · STALE >10min · UNAVAILABLE = provider call failing / kill-switch engaged (last-known values shown, explicit banner, no new flags computed).

**Interface:**
```python
class MarketDataProvider(Protocol):
    def get_ticks(self, tickers: list[str]) -> list[Tick]: ...
    def get_status(self) -> ProviderStatus: ...
```

**Implementations:**
1. `HistoricalReplayProvider` — real yfinance OHLCV for ~30-50 NSE stocks, replayed/perturbed on a clock tick. Default and only provider — disclosed simulation.
   - Phase 1 implementation (`backend/app/providers/historical_replay.py`): a `ReplayClock` holds a single explicit step index, injected rather than wall-clock-driven, so replay is deterministic and testable. All tickers advance in lockstep on that one shared index. `get_ticks()` returns each requested ticker's historical observation at the current step, re-tagged `source="replay_simulated"` — the underlying price/volume values are always real historical data loaded from `price_ticks` (`source="real_historical"`), never randomly generated. No NSE trading-hours modeling yet; that's a later phase.
2. `FaultInjectingProvider` — **decorator around #1**, not a separate path. `POST /admin/fault {mode: outage|stale|recover}`:
   - `outage` → `get_ticks()` raises / `get_status()` → `UNAVAILABLE`
   - `stale` → freezes the clock the replay provider reads from; `age_seconds` grows naturally past thresholds — real freshness logic reports it, not a fake label
   - `recover` → unfreezes; scheduler's next tick triggers **incremental** recomputation (only what changed since the frozen point)

This must exercise the exact same code path a real outage would hit — that's what makes the live demo defensible under "is that faked?" scrutiny.

## API design

| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/watchlists` | create watchlist | |
| POST | `/watchlists/{id}/items` | add ticker | idempotent upsert on PK |
| DELETE | `/watchlists/{id}/items/{ticker}` | remove ticker | |
| GET | `/watchlists/{id}/digest` | current flags + freshness state | Returns `ETag` header = aggregate hash; client sends `If-None-Match` → 304 if unchanged. Phase 3 implemented (`app/routers/watchlists.py`); `freshness` is hardcoded `"LIVE"` until Phase 4 wires real provider status. |
| POST | `/watchlists/{id}/ack` | ack specific flag IDs | `{flag_ids: [...]}` — no client-supplied hash accepted; server always recomputes authoritative hash, never trusts client's. Phase 3 implemented. |
| GET | `/tickers/{ticker}/evidence?flag_id=` | "show your work" data | `{ticker, window_start, window_end, mean_return, stdev_return, points: [{date, return, price}], flagged_point: {date, return, z_score}}` — frontend draws directly, no client-side stats recomputation. Phase 3 implemented (`app/services/evidence.py`); `mean_return`/`stdev_return`/`points` come from the exact same baseline row (`load_latest_baseline`) that produced the flag's stored `z_score` — not independently recomputed — so the displayed band and the displayed z_score are always algebraically consistent (reproducible within floating-point tolerance, tested). The flagged day's own return is fetched separately and may fall outside the plotted `points` window, since the baseline is static (Phase 2). |
| GET | `/provider/status` | current freshness state | polled for the freshness banner |
| POST | `/admin/fault` | demo-only fault injection | gated behind `DEMO_MODE` env flag, 404/403 otherwise |
| GET | `/metrics` | ETag short-circuit rate (stretch) | |

**Idempotency:** `POST /items` upserts on composite PK. `POST /ack` uses `ON CONFLICT DO NOTHING` — safe to replay, which is what makes refresh-mid-ack and duplicate requests safe by construction.

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
│   │   └── 001_init.sql     # numbered SQL files applied manually via `psql -f`, no migration tool for this build
│   ├── scripts/
│   │   ├── seed_historical_data.py   # one-off manual backfill: yfinance -> tickers/price_ticks -> baselines
│   │   └── smoke_test_replay.py      # one-off manual check: replay real seeded data, confirm source='replay_simulated'
│   ├── tests/                # pytest + pytest-asyncio; DB-backed tests run against real local Postgres
│   └── app/
│       ├── main.py          # FastAPI app + CORS + lifespan (DB pool)
│       ├── config.py        # pydantic-settings, reads .env
│       ├── db.py            # asyncpg pool
│       ├── auth.py          # demo-user identity seam (get_current_user, DEMO_USER_ID)
│       ├── schemas.py       # Pydantic request bodies (WatchlistCreate, AckRequest, ...)
│       ├── data/
│       │   ├── tickers.py   # fixed TICKER_SECTORS universe + to_nse_symbol()
│       │   └── baselines.py # rolling-window baseline computation
│       ├── providers/
│       │   ├── base.py               # Tick, ProviderStatus, MarketDataProvider protocol
│       │   └── historical_replay.py  # HistoricalReplayProvider + ReplayClock
│       ├── services/
│       │   ├── scoring.py            # deterministic scoring engine (Phase 2)
│       │   ├── flags.py              # severity-escalation ack-bust upsert (Phase 2)
│       │   ├── digest.py             # aggregate ETag hash + unacked-flags query (Phase 3)
│       │   ├── watchlist_access.py   # ownership check (Phase 3)
│       │   └── evidence.py           # "show your work" evidence builder (Phase 3)
│       └── routers/
│           ├── health.py       # GET /health (real SELECT 1)
│           ├── watchlists.py   # POST /watchlists, /items, GET /digest, POST /ack (Phase 3)
│           └── tickers.py      # GET /tickers/{ticker}/evidence (Phase 3)
└── frontend/                # Next.js (App Router) + Tailwind, standard create-next-app layout
```
