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
- [ ] Backend: scoring engine (z-score, volume ratio, sector tag)
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
1. **Phase 1 is complete and verified against real data.** Decide whether to retry `TATAMOTORS.NS` (currently absent — Yahoo 404) via a re-run of the seed script (safe/idempotent) or accept 34/35 for the demo universe.
2. Finish Stage 5 (frontend UX + exact demo script) — quick pass, don't over-invest more planning time.
3. Phase 2: scoring engine (z-score/severity) + Digest API + ETag/ack flow, per DATA_MODEL.md's severity-escalation transaction rule.

## Recent changes
- Sep 4: Phase 0 scaffolded — backend (FastAPI, asyncpg, raw SQL, requirements.txt), frontend (Next.js/Tailwind via create-next-app), docker-compose (Postgres only), schema migrated via `backend/migrations/001_init.sql` (`psql -f`, no migration tool). `/health` verified locally: real `SELECT 1` round-trip, returns 200.
- Sep 4: Phase 1 (data layer) implemented — fixed ticker universe (`app/data/tickers.py`), historical backfill script (`scripts/seed_historical_data.py`), baseline computation (`app/data/baselines.py`), `HistoricalReplayProvider` + `ReplayClock` (`app/providers/`). 18 tests written and passing against real local Postgres.
- Sep 4: **Real backfill run (locally, outside the dev sandbox where Yahoo was rate-limited) — Phase 1 verified end-to-end against real data.** Results: 34/35 tickers succeeded (`TATAMOTORS.NS` failed — Yahoo 404/no data, correctly absent from `tickers`/`price_ticks`/`baselines`, no fabricated substitute), 8,567 `real_historical` price_ticks (0 duplicates on `(ticker, ts, source)`), 34 baselines all with `sample_size=30` (well above the 20-day confidence gate), `M&M.NS` and `BAJAJ-AUTO.NS` special-character symbols resolved correctly. Replay-provider smoke test (`scripts/smoke_test_replay.py`) run against the real seeded data: emitted ticks used real historical prices in chronological order, all tagged `source='replay_simulated'`. One real-data quirk observed and preserved as-is (not a bug): `M&M.NS` on 2025-09-08 has a repeated close price and `volume=0` as reported by yfinance itself.

## Known bugs / roadblocks
- yfinance/Yahoo Finance was network-blocked (HTTP 429) from the Claude Code dev sandbox during Phase 1 development — resolved by running the seed script locally instead (see Sep 4 backfill entry above). Not a code defect; no fix needed, just noting why the backfill was run outside the sandbox.
- `TATAMOTORS.NS` — Yahoo returns 404/no data for this symbol. Correctly excluded from all tables (no fabricated row anywhere), universe currently effectively 34/35. Worth a periodic retry (yfinance/Yahoo symbol issues are sometimes transient) but not blocking.

## Open decisions still needed
- Exact frontend component structure (Stage 5)
- Which 30-50 tickers make up the fixed universe, and the hand-curated sector buckets
