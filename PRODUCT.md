# Product decisions — locked, do not re-litigate

## Direction (confirmed after two independent brainstorming passes)
**Signal Digest.** Rank/flag changes by statistical unusualness relative to each instrument's own recent volatility/volume baseline — not raw % move, not a global threshold. Explanation is the product; ranking is a side effect of having one. Do not drift into "ranked top-N + hide the rest" as the whole UI — that pattern was independently flagged as backend-thin and rejected.

Secondary signal, not a dependency: sector-relative context (bucket the fixed stock universe into 4-6 hand-curated sectors, compare a flagged stock's move to its sector's own mean move for the day). Must degrade gracefully to "no sector context" — never blocks the core flag.

## Why this exists vs. Groww's real watchlist
Groww's existing watchlist answers "what's the price now." This answers "does this deserve your attention, and why" — by comparing every move to that instrument's own normal behavior instead of a one-size-fits-all threshold.

## Data source — locked
- Groww's real Trading API exists (`growwapi`) but requires an active F&O-enabled account + ₹499/month subscription — not viable in this window, don't depend on it. Mention it in the README as "the production integration path" only.
- Use `yfinance` (.NS/.BO suffixes) for real historical OHLCV, no key required. Pull real history once for ~30-50 liquid NSE stocks, compute baselines offline, replay/perturb to simulate live ticks. Disclosed simulation, real underlying data — never claim it's live.

## Why deterministic scoring, not AI/ML
Explicit rejection of ML-for-novelty. Z-score crossing ±2.0 on rolling 20-30 day return is the primary trigger; volume ratio and sector context are annotations, not folded into a composite weighted score (defensibility in Q&A: one number + plain English beats justifying arbitrary weights). Groww's own AI assistant (GR 1, launched at Groww Next 2026) is positioned as "informative, not autonomous" with explicit consent/execution guardrails — cite this precedent if asked "why no AI": right tool for the job, same principle the host company applies to its own AI.

The *only* acceptable optional LLM use: phrasing the one-line natural-language explanation from an already-computed structured signal (z_score, volume_ratio, sector_relative). Never touches decision logic. Cut first under time pressure — deterministic string template is the default target, not a fallback.

## `volatility_regime` is computed but not surfaced in the digest — deliberate, not a bug

`signal_type = 'volatility_regime'` (stdev_5d/stdev_30d ratio crossing 1.5) is still computed and persisted by the scoring engine exactly as designed — nothing about its computation changed. Live testing (Phase 5/6) surfaced a real UX problem: because baselines are static (Phase 2's documented simplification — one baseline row per ticker, not recomputed per replay day), the same handful of tickers whose end-of-window stdev ratio happens to cross the trigger flag on *every single replay cycle*, with the same generic explanation text each time. That's repetitive noise, not a meaningful "something changed" signal, in a build without rolling baselines.

Resolution: `GET /watchlists/{id}/digest` filters to `signal_type = 'price_zscore'` only (`backend/app/services/digest.py`). No rows are deleted, no scoring logic touched — this is purely a display decision, reversible in one line once rolling baselines exist (a natural extension, not planned for this build). The digest is also explicitly ranked by `|z_score|` descending, most statistically unusual first, now that price_zscore is the digest's only signal type.

## "Since you last checked" — design precedent
Modeled explicitly on two real Groww engineering blog posts (tech.groww.in):
- **"Improving the Efficiency of Rendering User Holdings"** — ETag-as-fingerprint-of-state, cached in Redis, `304 Not Modified` short-circuit when unchanged. Our equivalent: `watchlist_ack_state.last_seen_hash` + real HTTP `ETag`/`If-None-Match` semantics on `GET /digest`.
- **"Holding Revamp Went Live. Then Reality Check Hit Hard"** — the Ghost ETag bug: invalidating cache *before* transaction commit created a race window. Our fix, applied proactively rather than discovered in production: ack-busting on severity escalation happens in the same transaction as the flag upsert, and cache invalidation semantics generally happen after-commit, never on trigger.

Cite these explicitly in the README and in Q&A — it's a legitimate, checkable claim, not generic hackathon talk.

## Demo differentiation — committed, not optional
1. **Live fault injection.** `/admin/fault {mode: outage|stale|recover}` (DEMO_MODE-gated) wraps the real data provider via decorator, not a separate code path — killing the feed live triggers the same STALE/UNAVAILABLE logic a real outage would. This is the top demo beat: proves Reliability + Edge Cases + Engineering Depth live.
2. **"Show your work" panel.** Clicking a flag renders the actual rolling-return distribution (mean/stdev band + today's point plotted outside it) via `GET /tickers/{ticker}/evidence`. Proves "auditable statistics, not black box" visually — the thing a generic threshold watchlist can't show.
3. **Combined beat (Stage 3's addition, keep this exact sequencing):** freeze clock (stale) → ack a "notable" flag on screen → resume clock, same ticker moves further → flag flips back to unacked and escalates to "extreme" live, driven by the severity_rank comparison, not scripted. Stronger than outage/recovery alone because it proves a subtle correctness rule, not just uptime.

Stretch/cut-first: live ETag short-circuit % counter on screen; live two-tab reconciliation shown on screen.

**Demo time discipline:** the 5-minute demo features at most the digest+evidence panel and the combined fault-injection/escalation beat. Every other failure scenario in RELIABILITY.md is a Q&A answer, not a live narration — don't try to be comprehensive on stage.
