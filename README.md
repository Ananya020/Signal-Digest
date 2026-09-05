# Signal Digest

A watchlist that flags price/volume moves which are statistically unusual **for that specific instrument's own recent behavior** — not a flat percentage move, not a global threshold — and shows the reasoning behind every flag, not just a number.

## 1. Problem

The obvious reading of "smart watchlist" is a price ticker with a search box and maybe a percent-change column. That's what Groww's watchlist already does, and it has a real failure mode: every row is rendered with equal visual weight, and every move is judged against the same flat threshold regardless of what's normal for that instrument. A 2% move in a historically stable FMCG stock and a 2% move in a volatile mid-cap Auto name are not the same event — a flat-threshold watchlist can't tell them apart, so it either floods you with noise or misses the thing that actually matters. The brief's own framing is exact: don't build the obvious watchlist, build the version you believe should exist, and be ready to explain why.

## 2. Product thesis

Groww's real watchlist answers "what's the price now." Signal Digest answers **"does this deserve your attention, and why"** — by comparing every move to that instrument's own normal behavior instead of a one-size-fits-all threshold.

> **Core user promise:** Open your watchlist and know in five seconds what actually changed — not what always jitters — and why.

## 3. Key insight

Meaningful change is relative to an instrument's own normal behavior, not an absolute number. A z-score crossing does that arithmetic once per ticker, per day, against that ticker's own rolling baseline. The explanation — "2.9σ above normal, on 2.3× typical volume, moving independently of its sector" — **is the product**; the ranked list is a side effect of having a real, comparable number to sort by, not the other way around.

## 4. Architecture

```
Next.js Frontend (Dashboard/Digest, Evidence panel, Freshness banner, Fault-injection demo control, Watchlist manager, Historical changes log, About panel)
        │ HTTPS JSON
        ▼
FastAPI Backend — single modular monolith
  ├─ API layer (routers) — demo-user identity seam, ownership-checked watchlist endpoints
  ├─ Digest Service — fetch flags, compute/verify aggregate ETag, ack handling (after-commit only)
  ├─ Scoring Engine — z-score, volume ratio, sector tag, severity band, sample_size gate
  ├─ Data Provider Abstraction — HistoricalReplayProvider, decorated by FaultInjectingProvider
  └─ Background Scheduler (APScheduler) — periodic tick + scoring, one job, one interval
        │
        ▼
PostgreSQL
```

**Why a modular monolith, not microservices.** This is a direct, deliberate response to the Ghost ETag precedent (Groww's own postmortem — see §7): the bug that shipped was a *transaction-boundary* problem — a cache invalidation that fired before its write had committed, across a boundary that made "before" and "after" ambiguous. Splitting this system into services (a scoring service, a digest service, a notification service) reintroduces exactly that boundary — the ack-bust-in-the-same-transaction guarantee this project treats as its single most important correctness rule (§6) cannot be a cross-service invariant without a distributed transaction or a saga, both of which are the wrong tool for a system this size. One process, one database, one transaction boundary was the actual engineering call, not a shortcut.

**Data provider abstraction.** `MarketDataProvider` is a two-method protocol (`get_ticks`, `get_status`). `HistoricalReplayProvider` is the only real implementation: it replays real historical closes chronologically via an explicit, injectable `ReplayClock` (not wall-clock-driven, so it's deterministic and testable). `FaultInjectingProvider` wraps it as a **decorator, not a fork** — `outage`/`stale`/`recover` change what the same `get_ticks()`/`get_status()` calls return, so a live demo kill-switch exercises the identical code path a real provider outage would hit, not a special demo branch.

**yfinance vs. Groww's real Trading API.** Groww's real API (`growwapi`) exists and is the honest production integration path — but it requires an active F&O-enabled account and a ₹499/month subscription, which wasn't viable to depend on for this build. `yfinance` pulls real historical OHLCV for the fixed NSE universe with no key required; that real history is replayed/perturbed on a clock tick to simulate live ticks. This is disclosed simulation over **real underlying data** — deliberately not synthetic/random price generation, because the entire scoring engine's credibility depends on the numbers being real.

**Optional second provider — `LiveDelayedNSEProvider`, opt-in, off by default.** There's no legitimate free live NSE feed (Zerodha's Kite Connect needs a KYC'd trading account + static IP; unofficial NSE scrapers are undocumented and currently reported broken). This provider exists to prove the `MarketDataProvider` abstraction generalizes to a genuinely unreliable real source, not to solve that unsolvable problem — see PRODUCT.md's "Data source" section for the full, honest writeup (including the real, unmocked verification: a direct NSE scrape 403s immediately, while `yfinance`'s intraday endpoint returned real delayed data). Gated behind `LIVE_PROVIDER_ENABLED=false`, orthogonal to `DEMO_MODE`, never wired into scoring — status-only via `GET /provider/live-status`.

## 5. The meaningful-change algorithm

- **Primary trigger:** price z-score, `(today_return − mean_return_30d) / stdev_return_30d`, crossing `|z| ≥ 2.0`. Severity bands: `notable` (2.0–2.5), `significant` (2.5–3.5), `extreme` (≥3.5).
- **Annotations, never folded into the trigger:** volume ratio (`today_volume / avg_volume_30d`, `None`/"unknown" rather than a fabricated `0x` on a missing tick) and sector-relative context (`sector_wide` vs. `stock_specific`, `NULL` when fewer than 2 other sector members have a valid tick that cycle — never computed off a partial sector). Both are annotations on the z-score-driven flag, never averaged or weighted into one composite score. The reason is defensibility: one number plus plain English beats justifying arbitrary weights in a Q&A.
- **Confidence gate:** `baselines.sample_size < 20` suppresses a flag entirely rather than emitting a confident-looking number off a handful of days of history.
- **`volatility_regime` is computed and stored but still not surfaced in the digest — the reason has changed, and this is the current, accurate one, not the original.** It's a real secondary signal (`stdev_5d`/`stdev_30d` crossing 1.5). It was originally hidden because static baselines made it repetitive noise (the same handful of tickers, every cycle) — that's **resolved**: baselines now roll forward per trading day (§6/§8), and a real 20-cycle replay run confirmed the flagged-ticker set genuinely rotates day to day (e.g. a `RELIANCE.NS`/`ICICIBANK.NS`/`WIPRO.NS`/`NESTLEIND.NS` cluster for several consecutive days, then a shift to `NTPC.NS`/`POWERGRID.NS`, then `MARUTI.NS`/`ADANIENT.NS`/`ASIANPAINT.NS`). It stays out of the digest anyway, for a different, concrete reason: two things now assume the digest is exclusively `price_zscore` with a non-null `z_score` — the digest's own `ORDER BY abs(z_score) DESC` ranking, and Today's Brief's "strongest signal"/direction facts (below) — and `volatility_regime` has no z-score at all. Re-enabling it means deciding how those two consumers should treat a non-directional signal first, not just deleting the SQL filter — see PRODUCT.md for the full writeup.
- **"Today's Brief"** — a short (1–3 sentence), fully deterministic synthesis of the current unacknowledged signals, added as a `brief` field on `GET /digest`'s existing response (see §6 for why this endpoint, not a separate one). Pure aggregation over the same rows the digest already returns (counts by severity/sector, the single strongest signal, direction split) plus fixed string templates — no LLM, no network call, no external dependency of any kind, so there's no timeout/fallback logic to write because there's nothing external that can fail. Read-only and computed strictly after the digest; it cannot influence severity, ranking, or ack-bust. `null` with zero active signals — the existing empty-state copy is unchanged. See PRODUCT.md for the full template-branch writeup and why this is distinct from the separately-scoped, still-unbuilt optional LLM-phrasing layer (§8).

## 6. Data model

- `price_ticks` — immutable source of truth; needed to recompute anything after a fault-recovery.
- `baselines` — precomputed ahead of scoring, not derived per-request (the "rebuild on every read" anti-pattern Groww's own Holdings post is explicitly about). One row per `(ticker, as_of_date)`, rolled forward once per scheduler cycle before that cycle's ticks are scored — not a single static row per ticker (see §8).
- `flags` — durable record of *why* something was surfaced; backs the evidence endpoint and the uniqueness constraint that prevents duplicate flags.
- `flag_ack` / `watchlist_ack_state` — split deliberately: the aggregate hash is a cheap ETag-style short-circuit; the per-flag table is the fine-grained truth for "which specific things are new."

**"Today's Brief" extends `GET /digest`'s existing response rather than adding a new endpoint.** `GET /digest` already fetches exactly the rows the brief needs (ticker, severity, z_score, sector) in one query; a separate `GET /brief` would either re-run that same query or require the client to pass the digest's own data back in — either way, more moving parts for zero benefit, since (unlike an LLM call) there's no cost/latency reason to decouple them. One added field, one join (`flags` → `tickers` for the sector name), no new route, no new polling hook.

### Severity escalation busts the ack — the project's single most defensible correctness decision

`flags` upserts on `(ticker, trading_day, signal_type)`; `flag_ack` keys on the constant `flag_id`. Without a deliberate fix, a flag that escalates from `notable` to `extreme` intraday would stay silently acked even though it's a genuinely new qualifying event. The fix: reading the previous `severity_rank`, upserting the flag's evidence unconditionally, and — in the **same transaction** — deleting the `flag_ack` row if and only if the new rank is strictly greater than the previous one.

This is deliberately **asymmetric**: escalation busts the ack; de-escalation does not. An ack means "the user has seen and dismissed this level of concern." Worse-than-dismissed is new information and must resurface. Better-than-dismissed has no new concern to raise — staying acked is correct, not an oversight.

(This exact rule was caught drifting once during development — see §12 — and fixed via a real Postgres `RETURNING`-behavior test before it ever reached production behavior, not discovered after the fact.)

## 7. Since-you-last-checked / reliability

The digest's state machine is modeled explicitly on two real Groww engineering posts (tech.groww.in):

- **"Improving the Efficiency of Rendering User Holdings"** — ETag-as-fingerprint-of-state, `304 Not Modified` short-circuit when unchanged. Our equivalent: a SHA-256 hash of the watchlist's current unacknowledged `(flag_id, severity_rank)` set, served as a real HTTP `ETag` with `If-None-Match` semantics on `GET /digest`.
- **"Holding Revamp Went Live. Then Reality Check Hit Hard"** — the Ghost ETag bug: invalidating cache *before* the write that should have triggered it had committed, opening a race window. Our proactive equivalent: the ack-bust delete happens in the same transaction as the flag upsert, reading only committed state, never on a pre-commit trigger.

**Live fault injection** (`POST /admin/fault {mode: outage|stale|recover}`, `DEMO_MODE`-gated) is a decorator over the real provider (§4) — killing the feed live triggers the same `STALE`/`UNAVAILABLE` state-machine logic a real outage would, not a scripted demo branch. `stale` freezes the replay position but never the age clock — `age_seconds` is always real wall-clock time since the last successful fetch, which is what makes `STALE` a real state rather than a label.

A few of the more interesting failure scenarios (full list of 14 in `RELIABILITY.md`; the rest are Q&A material, not live narration):

| Scenario | Why it's interesting |
|---|---|
| Recompute/ack race (Ghost-ETag-shaped) | The actual cited precedent — ack-bust reads committed state only, one transaction, never a pre-commit hook. |
| Timezone bucketing | `trading_day` must be computed in Asia/Kolkata, not UTC-naive. A real gap was found here (see §12) and fixed with a dedicated boundary test. |
| Partial ingestion (scheduler dies mid-batch) | Each ticker's flag upsert is its own committed transaction — a mid-batch failure never rolls back tickers already scored, and a retry can't duplicate them. |
| Sector aggregation with missing members | Sector mean is computed only over tickers with a valid tick *that cycle* — fewer than 2 live peers and the tag is `NULL`, never computed off a partial sector. |
| Stale `If-None-Match` after days away | The server always recomputes the hash server-side — a client returning with an ancient ETag just gets a full `200`, no special-cased logic required. |
| Ack references a deleted/superseded flag | Existence-checked before insert; a bad id is ignored, not a hard failure for the whole request. |

## 8. Trade-offs

- **Deterministic scoring over ML/LLM.** An LLM-flavored watchlist is the generic 2026 move, not the differentiated one — Groww's own AI assistant (GR 1) is positioned as "informative, not autonomous," and this project applies the same principle to its own core decision logic. The one narrow, optional LLM use case that was scoped out: phrasing the one-line explanation from an already-computed structured signal — never touching decision logic, and cut first under time pressure in favor of the deterministic template that's actually shipped.
- **Modular monolith over microservices** — see §4; a service split reintroduces the exact transaction-boundary bug class this design proactively avoids.
- **yfinance over Groww's live Trading API** — see §4; real data, disclosed simulation, no viable path to a paid F&O account in this window.
- **Rolling, look-ahead-safe baselines — no longer a static simplification.** A baseline for trading day N is recomputed each scheduler cycle from only the days strictly before N (`compute_baseline_as_of`), stored as a new `(ticker, as_of_date)` row rather than overwritten in place — so day N's own move never leaks into its own baseline, and `sample_size` genuinely reflects how much history existed before that day (observed growing from 24 toward the 30-day cap across early replay days in a real run, not a fixed 30 from day one). This replaces the earlier one-row-per-ticker static baseline, and is what made `volatility_regime`'s output worth re-examining (§5).

## 9. Scalability

- The ETag short-circuit means a client with an unchanged view gets a `304` without the server ever running the unacked-flags join — at real scale, that's the difference between recomputing a digest on every poll and skipping the query entirely.
- Baselines are batch-computed once, not derived per-request — the anti-pattern the Holdings post itself is about.
- What would actually need to change for real scale: incremental (not full-recompute-per-cycle) baseline maintenance as the universe or tick rate grows (§8); a real live market data feed in place of the replay provider; and a ticker universe that isn't fixed at 35 hand-curated names (today's sector tagging and universe validation both assume a small, known set).

## 10. Setup

```bash
# 1. Postgres
docker compose up -d postgres

# 2. Schema (numbered SQL files, applied manually — no migration tool)
docker compose exec -T postgres psql -U user -d signal_digest < backend/migrations/001_init.sql
docker compose exec -T postgres psql -U user -d signal_digest < backend/migrations/002_add_last_successful_fetch.sql

# 3. Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp ../.env.example .env   # fill in DATABASE_URL etc.

# 4. Historical data (one-off, real yfinance pull — takes a few minutes)
python -m scripts.seed_historical_data

# 5. Run the backend (scheduler starts automatically with the app)
uvicorn app.main:app --reload
# confirm: GET /health -> {"status":"ok"}; GET /provider/status -> state advances on its own every SCHEDULER_INTERVAL_SECONDS (default 5s)

# 6. Frontend
cd ../frontend
npm install
npm run dev   # http://localhost:3000
```

`DEMO_MODE=true` in `.env` gates `POST /admin/fault` — with it unset, that route 404s unconditionally at the route level, before touching the provider or DB. It also controls whether the frontend renders the fault-injection demo control at all (via `/provider/status`'s `demo_mode` field).

**Resetting to a clean slate** (e.g. before a demo rehearsal): `python -m scripts.reset_demo_state` truncates `flags`/`flag_ack`/`watchlist_ack_state` and resets `provider_state` to normal. It never touches `tickers`/`price_ticks`/`baselines` (real seeded data) or `watchlists`/`watchlist_items` (user-created state).

## 11. Testing

**150 backend tests** (pytest, real Postgres — not mocks, for anything touching a transaction boundary) + **46 frontend unit/component tests** (vitest) = **196 tests**, all currently passing — plus one real end-to-end test (Playwright, below) that isn't counted in that number because it's a different tier entirely (a live browser against a live backend, not an isolated unit). A few that actually prove something non-obvious, not just exercise a happy path:

- **The ack-bust escalation/de-escalation pair** (`test_flags_ack_bust.py`) — one test proves escalation busts the ack; a second, explicitly a "negative-space" test, proves de-escalation does *not* — the asymmetry in §6 is enforced code, not just a design doc claim.
- **The `RETURNING`-behavior test from the Phase 2 correction** (`test_postgres_returning_yields_zero_rows_when_conflict_where_is_false`) — asserts, against real Postgres, the exact row-count `RETURNING` yields when an `ON CONFLICT DO UPDATE ... WHERE` clause evaluates false. That single fact is what caught the original ack-bust upsert conflating "should the ack be busted" with "should the evidence refresh" — a bug in the originally-documented SQL, caught before it shipped.
- **The timezone boundary test** (`test_reliability_timezone.py`) — a tick timestamped 19:30 UTC (already 01:00 IST the next calendar day) must bucket into the correct IST trading day, not the UTC one. This test caught a real bug: `trading_day` was computed with `.date()` directly on a UTC-aware timestamp, masked in production data only because the real ingestion path happens to anchor at 15:30 IST — safely mid-day.
- **The look-ahead-safety test for rolling baselines** (`test_compute_baseline_as_of_excludes_the_scored_day_own_move`) — seeds a violent price move on the exact day being scored and asserts that day's own baseline shows no trace of it, then cross-checks against the naive (look-ahead-*unsafe*) full-series computation to prove the difference is real, not incidental.
- **The Today's Brief end-to-end test** (`test_brief_updates_as_flags_are_acked_down_to_one_then_zero`) — asserts the brief's template branch changes correctly as real flags are acked away: concentrated-sector wording with two active signals, the single-signal sentence once one remains, then `null` once the last one is acked — proving the brief tracks real committed digest state, not a snapshot taken once.

### E2E demo rehearsal (Playwright)

A single automated test (`frontend/e2e/demo-rehearsal.spec.ts`) walks the entire live demo script (see PROGRESS.md's "Canonical demo script") against a **real** running backend, **real** Postgres, and the **real** frontend — no mocks anywhere, since the whole point is catching real integration issues a mocked test can't. It proves demo-readiness is verifiable by running one command, not just by a human rehearsing it.

**Run it:**
```bash
docker compose up -d postgres   # prerequisite — not started by the test itself
cd frontend
npm run test:e2e
```
Playwright starts the backend and frontend dev servers itself if they aren't already running (`reuseExistingServer: true` — it happily attaches to servers you already have up instead of double-starting; the backend it starts itself uses `DEMO_MODE=true` and a compressed `SCHEDULER_INTERVAL_SECONDS=2` for a faster rehearsal).

**What it does, end to end, against real state:**
1. Resets demo state (`scripts.reset_demo_state`) and fast-forwards **real** scoring (`scripts.run_scoring_once`) so the digest has real flags immediately.
2. Loads the dashboard fresh — asserts `LIVE` freshness and a real flag row with a real rendered z-score.
3. Opens the evidence panel — asserts the real computed mean/stdev/z-score stats render, not placeholders.
4. Acknowledges that flag — asserts it disappears from the unacked view.
5. Triggers Outage — asserts freshness flips to `UNAVAILABLE`; triggers Recover — asserts it returns to `LIVE`.
6. Finds a real, not-yet-reached (ticker, trading day) that genuinely crosses `extreme` (a new helper, `scripts.find_escalation_candidate`, scans the real seeded history the same look-ahead-safe way the live pipeline scores it — dynamically, since where a fresh vs. long-running server's replay clock currently sits isn't knowable ahead of time), seeds the escalation-flip precondition (`scripts.seed_demo_escalation_precondition`), then waits for the **real live scheduler** to naturally reach that day and asserts the flag reappears unacknowledged at the exact severity/z-score the setup step independently pre-verified — not just "some flag appeared."
7. Asserts Today's Brief updates to name that ticker, reflecting the real post-escalation state.

**Verified real, twice**: two full runs (plus a third via the documented `npm run test:e2e` command) all passed, ~34s each. The escalation-wait step (6) is the one genuinely timing-sensitive part — bounded to 150s, not indefinite — but see the code comment on `waitByPullingInNewSignals` in the spec file for why a fixed sleep there would be the wrong tool: the digest deliberately buffers background updates behind a "Show N new signals" affordance (Stage 2 UX design), so the test polls and clicks that affordance on a short interval until the escalated flag actually renders, rather than guessing one delay.

**A real bug found and fixed while building this test**: neither `scripts/seed_demo_escalation_precondition.py` nor the new `scripts/find_escalation_candidate.py` originally checked the scoring pipeline's own `sample_size < MIN_SAMPLE_SIZE` confidence gate before "verifying" a day's real severity — meaning either script could have picked a day the real pipeline would actually suppress, seeding a placeholder that could never be corrected (a live demo hanging on stage waiting for a flip that can't happen). Both now enforce the identical gate `score_price_zscore()` uses; regression-tested (`test_escalation_scripts_sample_size_gate.py`).

## 12. Known limitations

Stated plainly, not hedged:

- **`volatility_regime` is computed and stored but still not surfaced in the digest — kept hidden for a concrete technical reason now, not the original UX one.** See §5: the repetitiveness that originally motivated hiding it is resolved, but the digest's z-score ranking and Today's Brief's z-score-based facts both currently assume every digest row is a `price_zscore` flag with a real z-score, which `volatility_regime` doesn't have.
- **Rolling baselines recompute from the full `price_ticks` history every cycle, not incrementally.** Each cycle re-derives each ticker's look-ahead-safe window from scratch (`load_price_series` + filter) rather than maintaining running sums — correct and simple at this scale (34 tickers, ~1 cycle/5s), but not the approach a much larger universe or a much shorter interval would want.
- **No walk-forward backtesting infrastructure.** Rolling recomputation is correct day-by-day, but there's no separate historical backtest harness beyond replaying the same live pipeline — out of scope for this workstream.
- **`TATAMOTORS.NS` is absent from the universe.** Yahoo Finance returned a 404/no-data response for this real symbol during the historical backfill — 34 of the 35 hand-curated tickers are seeded; no fabricated substitute was inserted.
- **Same-key severity escalation is architecturally deterministic under this build's daily-close replay, not intraday ticks.** `(ticker, trading_day, signal_type)` is scored from one fixed close against one fixed baseline — re-scoring the same trading day later always reproduces the identical z-score and severity, because neither input has changed. A production system fed real intraday ticks would see this fire organically within a session, as multiple ticks change that day's return-so-far. The ack-bust transaction itself is verified correct independent of this (§11, §6) — for a *live, on-stage* demonstration of the mechanism within a 5-minute window, `backend/scripts/seed_demo_escalation_precondition.py` seeds one flag at a deliberately-low placeholder severity for a real, not-yet-reached day (after independently verifying, with the real scoring functions, what that day's true severity will be), then lets the live scheduler correct it for real. This is disclosed here and in the script's own docstring — not presented as if it happened organically.

## 13. Future improvements

- Incremental baseline maintenance (running sums instead of a full-history recompute per cycle) if the ticker universe or scheduler interval scaled up meaningfully.
- Re-surfacing `volatility_regime` in the digest now that rolling baselines make its output genuinely non-repetitive (§5) — requires deciding how the digest's z-score ranking and Today's Brief's z-score-based "strongest signal"/direction facts should treat a signal type with no z-score, not just deleting the SQL filter.
- Real NSE trading-calendar/holiday gating (currently out of scope, not modeled).
- The optional LLM-explanation-phrasing layer (§8) — already architecturally isolated from decision logic, ready to slot in as a pure post-processing step.
- Multi-watchlist support (the data model already allows multiple watchlists per user; the frontend currently manages one).
- Real news/events signal integration.
- The ETag short-circuit hit-rate counter (cut as a stretch item, see `PRODUCT.md`).
- If a genuinely reliable live NSE feed ever becomes viable (a real Kite Connect subscription, or NSE's scrapeable surface stabilizing), deciding whether/how to feed `LiveDelayedNSEProvider`'s data into scoring — deliberately not done in this build (see PRODUCT.md's "Data source" section for why status-only was the safer choice).
