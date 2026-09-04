# Progress log — update after every significant work session

## Project overview
Signal Digest — see PRODUCT.md for full reasoning. Smart watchlist, per-instrument statistical anomaly flagging, ETag-pattern "since you last checked" state machine, live fault-injection demo.

## Current state
- [ ] Planning complete: Stages 1-4 done (product direction, scoring engine, state machine, architecture/schema, reliability review) — see PRODUCT.md, ARCHITECTURE.md, DATA_MODEL.md, RELIABILITY.md
- [ ] Stage 5 (frontend UX for 9 screens, exact demo script) — pending
- [ ] Stage 6 (feature prioritization, 72h execution plan, testing strategy, repo structure) — pending
- [x] Repo scaffolded (Phase 0: backend FastAPI skeleton, frontend Next.js skeleton, docker-compose for Postgres)
- [x] Backend: data provider abstraction — `HistoricalReplayProvider` done (`backend/app/providers/`); `FaultInjectingProvider` still pending (later phase)
- [x] Backend: schema migrated (including severity_rank fix) — `backend/migrations/001_init.sql`, applied and verified locally
- [x] Backend: fixed ticker universe + sector mapping (`backend/app/data/tickers.py`, 35 tickers, hand-curated, `.NS`-suffixed consistently everywhere)
- [x] Backend: historical backfill script (`backend/scripts/seed_historical_data.py`) — run successfully against real Yahoo Finance data, verified in Postgres (see Sep 4 entry below)
- [x] Backend: baseline computation (`backend/app/data/baselines.py`) — mean/stdev return, volume avg, sample_size gating, tested
- [x] Backend: scoring engine (z-score, volume ratio, sector tag, volatility_regime) — `backend/app/services/scoring.py`, deterministic, no ML/composite score, tested and run against real seeded data
- [x] Backend: severity-escalation ack-bust transaction — `backend/app/services/flags.py`, implemented exactly per DATA_MODEL.md, tested against real Postgres (escalation busts ack, de-escalation doesn't, equal-rank rerun is a no-op)
- [ ] Backend: digest API + ETag/ack flow
- [ ] Backend: evidence endpoint ("show your work")
- [ ] Backend: /admin/fault, DEMO_MODE-gated
- [ ] Frontend: digest view
- [ ] Frontend: evidence/distribution chart
- [ ] Frontend: freshness banner + fault-injection demo toggle
- [ ] Baseline data pulled (yfinance, ~30-50 NSE tickers, history computed)
- [ ] Demo script rehearsed
- [ ] README written (thesis, ETag precedent citation, trade-offs, limitations)
- [ ] 100-word pitch written

## Next steps (update this first, every session)
1. **Phase 2 is complete and verified against real data.** Decide whether to retry `TATAMOTORS.NS` (currently absent — Yahoo 404) via a re-run of the seed script (safe/idempotent) or accept 34/35 for the demo universe.
2. Phase 3: digest API + ETag/ack HTTP flow (`GET /watchlists/{id}/digest`, `POST /ack`), building on `flags`/`flag_ack` now populated by Phase 2's scoring service.
3. Phase 3/4: wire the actual APScheduler background job that drives the replay clock + scoring continuously — Phase 2 deliberately used a manual script instead (see architecture note below).
4. Before Phase 3/4's live demo: baselines are currently static (one row per ticker, computed once from the full ~1y history) — decide whether the demo needs per-day rolling baselines recomputed as the replay clock advances, or whether the static-baseline simplification is acceptable for the 72h scope. Currently causes `volatility_regime` to fire identically on every replay day for the same handful of tickers (AXISBANK, ADANIENT, ITC, NESTLEIND, ASIANPAINT, MARUTI, SUNPHARMA) — real behavior given the simplification, not a bug, but probably too repetitive for a live demo.
5. Finish Stage 5 (frontend UX + exact demo script) — quick pass, don't over-invest more planning time.

## Architecture notes carried forward to Phase 3/4

**`trading_day` derives from the replay tick's own timestamp, never wall-clock time.** `scoring.trading_day_from_tick()` returns `tick.timestamp.date()`. Replay ticks carry real historical dates; using `datetime.now().date()` would collide every ticker's entire replayed history onto a single real-world date and violate `UNIQUE(ticker, trading_day, signal_type)` in confusing ways. Tested explicitly (`test_trading_day_uses_historical_tick_date_not_wallclock_today`) and confirmed in the real run (flags carry dates like `2025-09-05`, not `2026-09-04`).

**Manual trigger script, not a scheduler, for Phase 2.** `backend/scripts/run_scoring_once.py` advances `HistoricalReplayProvider`'s explicit `ReplayClock` by N steps and scores each tick — no APScheduler wired yet. Decision: keep the scoring engine and the ack-bust transaction as the only things under test in Phase 2; introduce the actual background scheduler in Phase 3/4 once the API and `/admin/fault` need a live running process. The scoring service itself (`app/services/scoring.py`, `app/services/flags.py`) is scheduler-agnostic — Phase 3/4 can call it from an APScheduler job with no changes.

**Baselines are static across replay days (Phase 2 simplification, not a bug).** Phase 1's backfill computes exactly one baseline row per ticker (as of the last date in its ~1y history); Phase 2 does not recompute baselines per replay day. `load_latest_baseline()` documents this. Consequence: scoring an early replay day technically uses a baseline informed by later data (not walk-forward-correct), and any ticker whose end-of-window `stdev_5d/stdev_30d` ratio crosses 1.5 fires `volatility_regime` on literally every replayed day. Acceptable for Phase 2's scope (scoring math + ack-bust correctness); flagged above as a Phase 3/4 decision point for the live demo.

## Recent changes
- Sep 4: Phase 2 (core scoring engine) implemented — `app/services/scoring.py` (z-score, severity bands, volume ratio, volatility_regime, sector-relative tag, confidence gate), `app/services/flags.py` (severity-escalation ack-bust upsert, exact transaction from DATA_MODEL.md), `scripts/run_scoring_once.py` (manual trigger, not a scheduler). 19 new tests (13 pure scoring-math unit tests + 4 ack-bust transaction tests against real Postgres + 2 covered above), 37/37 total passing. Ran the manual script for 10 replay steps against Phase 1's real seeded data: 11 `price_zscore` flags and 70 `volatility_regime` flags emitted, all with real `trading_day` values from 2025 (not wall-clock "today"), 0 flags suppressed by the confidence gate (all 34 baselines have `sample_size=30`, none below the 20-day threshold). `TATAMOTORS.NS` correctly has no baseline and produced no flags (absent from Phase 1's seed, as expected).
- Sep 4: Phase 0 scaffolded — backend (FastAPI, asyncpg, raw SQL, requirements.txt), frontend (Next.js/Tailwind via create-next-app), docker-compose (Postgres only), schema migrated via `backend/migrations/001_init.sql` (`psql -f`, no migration tool). `/health` verified locally: real `SELECT 1` round-trip, returns 200.
- Sep 4: Phase 1 (data layer) implemented — fixed ticker universe (`app/data/tickers.py`), historical backfill script (`scripts/seed_historical_data.py`), baseline computation (`app/data/baselines.py`), `HistoricalReplayProvider` + `ReplayClock` (`app/providers/`). 18 tests written and passing against real local Postgres.
- Sep 4: **Real backfill run (locally, outside the dev sandbox where Yahoo was rate-limited) — Phase 1 verified end-to-end against real data.** Results: 34/35 tickers succeeded (`TATAMOTORS.NS` failed — Yahoo 404/no data, correctly absent from `tickers`/`price_ticks`/`baselines`, no fabricated substitute), 8,567 `real_historical` price_ticks (0 duplicates on `(ticker, ts, source)`), 34 baselines all with `sample_size=30` (well above the 20-day confidence gate), `M&M.NS` and `BAJAJ-AUTO.NS` special-character symbols resolved correctly. Replay-provider smoke test (`scripts/smoke_test_replay.py`) run against the real seeded data: emitted ticks used real historical prices in chronological order, all tagged `source='replay_simulated'`. One real-data quirk observed and preserved as-is (not a bug): `M&M.NS` on 2025-09-08 has a repeated close price and `volume=0` as reported by yfinance itself.

## Known bugs / roadblocks
- yfinance/Yahoo Finance was network-blocked (HTTP 429) from the Claude Code dev sandbox during Phase 1 development — resolved by running the seed script locally instead (see Sep 4 backfill entry above). Not a code defect; no fix needed, just noting why the backfill was run outside the sandbox.
- `TATAMOTORS.NS` — Yahoo returns 404/no data for this symbol. Correctly excluded from all tables (no fabricated row anywhere), universe currently effectively 34/35. Worth a periodic retry (yfinance/Yahoo symbol issues are sometimes transient) but not blocking.

## Open decisions still needed
- Exact frontend component structure (Stage 5)
- Which 30-50 tickers make up the fixed universe, and the hand-curated sector buckets
