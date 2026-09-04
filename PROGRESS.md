# Progress log — update after every significant work session

## Project overview
Signal Digest — see PRODUCT.md for full reasoning. Smart watchlist, per-instrument statistical anomaly flagging, ETag-pattern "since you last checked" state machine, live fault-injection demo.

## Current state
- [ ] Planning complete: Stages 1-4 done (product direction, scoring engine, state machine, architecture/schema, reliability review) — see PRODUCT.md, ARCHITECTURE.md, DATA_MODEL.md, RELIABILITY.md
- [ ] Stage 5 (frontend UX for 9 screens, exact demo script) — pending
- [ ] Stage 6 (feature prioritization, 72h execution plan, testing strategy, repo structure) — pending
- [ ] Repo scaffolded
- [ ] Backend: data provider abstraction (HistoricalReplayProvider + FaultInjectingProvider)
- [ ] Backend: schema migrated (including severity_rank fix)
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
2. Scaffold repo per ARCHITECTURE.md folder structure (once decided)
3. `.gitignore` + `.env.example` before first commit

## Recent changes
_(log here as you go — one line per session, e.g. "Sep 5: scaffolded FastAPI project, added provider abstraction skeleton")_

## Known bugs / roadblocks
_(none yet — log here as they appear, don't let them live only in chat history)_

## Open decisions still needed
- Exact frontend component structure (Stage 5)
- Which 30-50 tickers make up the fixed universe, and the hand-curated sector buckets
