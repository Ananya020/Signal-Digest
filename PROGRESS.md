# Progress log — update after every significant work session

## Project overview
Signal Digest — see PRODUCT.md for full reasoning. Smart watchlist, per-instrument statistical anomaly flagging, ETag-pattern "since you last checked" state machine, live fault-injection demo.

## Current state
- [ ] Planning complete: Stages 1-4 done (product direction, scoring engine, state machine, architecture/schema, reliability review) — see PRODUCT.md, ARCHITECTURE.md, DATA_MODEL.md, RELIABILITY.md
- [ ] Stage 5 (frontend UX for 9 screens, exact demo script) — pending
- [ ] Stage 6 (feature prioritization, 72h execution plan, testing strategy, repo structure) — pending
- [x] Repo scaffolded (Phase 0: backend FastAPI skeleton, frontend Next.js skeleton, docker-compose for Postgres)
- [ ] Backend: data provider abstraction (HistoricalReplayProvider + FaultInjectingProvider)
- [x] Backend: schema migrated (including severity_rank fix) — `backend/migrations/001_init.sql`, applied and verified locally
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
1. Finish Stage 5 (frontend UX + exact demo script) — quick pass, don't over-invest more planning time
2. Build data provider abstraction (HistoricalReplayProvider) + baseline computation
3. Digest API + ETag/ack flow, per DATA_MODEL.md's severity-escalation transaction rule

## Recent changes
- Sep 4: Phase 0 scaffolded — backend (FastAPI, asyncpg, raw SQL, requirements.txt), frontend (Next.js/Tailwind via create-next-app), docker-compose (Postgres only), schema migrated via `backend/migrations/001_init.sql` (`psql -f`, no migration tool). `/health` verified locally: real `SELECT 1` round-trip, returns 200.

## Known bugs / roadblocks
_(none yet — log here as they appear, don't let them live only in chat history)_

## Open decisions still needed
- Exact frontend component structure (Stage 5)
- Which 30-50 tickers make up the fixed universe, and the hand-curated sector buckets
