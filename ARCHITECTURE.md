# Architecture

## System diagram
```
Next.js Frontend (Dashboard / Digest / Detail / "show your work" chart / fault-injection demo toggle)
        │ HTTPS JSON
        ▼
FastAPI Backend — single modular monolith (not microservices; see CLAUDE.md for why)
  ├─ API layer (routers) + simple JWT auth (single demo account, no multi-tenant RBAC)
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
| GET | `/watchlists/{id}/digest` | current flags + freshness state | Returns `ETag` header = aggregate hash; client sends `If-None-Match` → 304 if unchanged |
| POST | `/watchlists/{id}/ack` | ack specific flag IDs | `{flag_ids: [...], client_hash}`; server always recomputes authoritative hash, never trusts client's |
| GET | `/tickers/{ticker}/evidence?flag_id=` | "show your work" data | `{ticker, window_start, window_end, mean_return, stdev_return, points: [{date, return, price}], flagged_point: {date, return, z_score}}` — frontend draws directly, no client-side stats recomputation |
| GET | `/provider/status` | current freshness state | polled for the freshness banner |
| POST | `/admin/fault` | demo-only fault injection | gated behind `DEMO_MODE` env flag, 404/403 otherwise |
| GET | `/metrics` | ETag short-circuit rate (stretch) | |

**Idempotency:** `POST /items` upserts on composite PK. `POST /ack` uses `ON CONFLICT DO NOTHING` — safe to replay, which is what makes refresh-mid-ack and duplicate requests safe by construction.

**Optional LLM explanation layer, if built:** `POST /internal/phrase` takes `{z_score, volume_ratio, sector_relative}`, returns a one-line string. Pure post-processing — never touches `flags` decision logic, trivially swappable for the deterministic template fallback.

## Folder structure
_(update this section once scaffolded — keep it current, not aspirational)_
