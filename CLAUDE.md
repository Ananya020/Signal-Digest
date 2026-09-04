# Signal Digest — Groww Code 2026

## Project overview
A smart market watchlist that flags price/volume moves which are statistically unusual *for that specific stock's own recent behavior* — not a flat % threshold — and shows the reasoning behind every flag, not just a number. Underneath, a rigorously-designed "since you last checked" state layer modeled on Groww's own published Holdings ETag pattern.

**Core user promise:** "Open your watchlist and know in five seconds what actually changed — not what always jitters — and why."

<important>
Before doing any non-trivial work, read (in this order): PRODUCT.md, ARCHITECTURE.md, DATA_MODEL.md, RELIABILITY.md, PROGRESS.md. Do not re-derive decisions already made in those files. If something in a request conflicts with a locked decision in PRODUCT.md, flag the conflict — don't silently override it.
</important>

## Tech stack
- Backend: Python, FastAPI, PostgreSQL, APScheduler (background jobs), Pydantic
- Frontend: Next.js, React, Tailwind (core utility classes only)
- Data: yfinance (.NS/.BO tickers) — real historical OHLCV, no API key. NOT Groww's live trading API (see PRODUCT.md for why).
- Deploy target: single modular monolith, one process. No microservices — not justified at this scale, and it would reintroduce the transaction-boundary bug class we're explicitly avoiding (see PRODUCT.md, Ghost ETag precedent).

<important>
## Rules of engagement
- Plan mode before every non-trivial feature: read the relevant .md files, then ask 3-5 clarifying questions about edge cases before proposing an approach. Don't skip this because a feature "seems simple."
- Deterministic scoring only in the core flag-decision path. No LLM, no ML model, in the z-score/severity logic — this is a stated design decision, not a placeholder. See PRODUCT.md.
- Every write to `flags` and `flag_ack` must happen inside the same transaction when severity escalation is involved (see DATA_MODEL.md) — this is the one correctness rule from the whole project that must never regress.
- `/admin/fault` and any other demo-only endpoint must be gated behind `DEMO_MODE` env var — must 404/403 when unset. Never remove this gate "to simplify."
- Verify any new package actually exists on PyPI/npm before installing it — do not install a package name you're not certain is real.
- No secrets in code, ever. Use `.env`, never commit it. Real values only in `.env`, template in `.env.example`.
- TypeScript/Python: prefer explicit types over inferred where it aids clarity; functional React components only.
- Keep responses focused: code + a short summary of what changed, not long explanations, unless I ask a design question.
</important>

## Where things live
See ARCHITECTURE.md for the folder structure and system diagram once scaffolded — update that file, not this one, as the structure solidifies.

## Current status
See PROGRESS.md — update it after every significant work session, not just at the end of the day.
