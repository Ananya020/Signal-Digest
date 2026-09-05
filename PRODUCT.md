# Product decisions — locked, do not re-litigate

## Direction (confirmed after two independent brainstorming passes)
**Signal Digest.** Rank/flag changes by statistical unusualness relative to each instrument's own recent volatility/volume baseline — not raw % move, not a global threshold. Explanation is the product; ranking is a side effect of having one. Do not drift into "ranked top-N + hide the rest" as the whole UI — that pattern was independently flagged as backend-thin and rejected.

Secondary signal, not a dependency: sector-relative context (bucket the fixed stock universe into 4-6 hand-curated sectors, compare a flagged stock's move to its sector's own mean move for the day). Must degrade gracefully to "no sector context" — never blocks the core flag.

## Why this exists vs. Groww's real watchlist
Groww's existing watchlist answers "what's the price now." This answers "does this deserve your attention, and why" — by comparing every move to that instrument's own normal behavior instead of a one-size-fits-all threshold.

## Data source — locked
- Groww's real Trading API exists (`growwapi`) but requires an active F&O-enabled account + ₹499/month subscription — not viable in this window, don't depend on it. Mention it in the README as "the production integration path" only.
- Use `yfinance` (.NS/.BO suffixes) for real historical OHLCV, no key required. Pull real history once for ~30-50 liquid NSE stocks, compute baselines offline, replay/perturb to simulate live ticks. Disclosed simulation, real underlying data — never claim it's live.

### Optional, opt-in second provider: `LiveDelayedNSEProvider` (Workstream 3, 2026-09-05)

Stated plainly, same honesty standard as above: **there is no legitimate free live NSE data source.** Zerodha's Kite Connect (₹500/month, down from ₹2000) requires an active KYC'd trading account and a static IP — neither obtainable in this build's timeframe. Unofficial NSE-website scrapers (e.g. `nsepython`) are explicitly undocumented/unsupported and have real, currently-reported breakage against NSE's own responses.

This workstream adds a second `MarketDataProvider` implementation anyway — not to solve the "no free live data" problem (it can't be solved), but to prove the provider abstraction (`get_ticks`/`get_status`, the same freshness state machine `FaultInjectingProvider` already uses) generalizes to a genuinely unreliable real source, not just the deterministic replay provider built for the demo.

**What it actually is:** `LiveDelayedNSEProvider` (`backend/app/providers/live_delayed_nse.py`) uses `yfinance` — the same library already vetted for the historical backfill — to fetch each ticker's most recent 1-minute intraday bar (`Ticker.history(period="1d", interval="1m")`). This is Yahoo's own exchange-delayed data (typically ~15 minutes during market hours; the prior session's last bar outside them), still unofficial/undocumented for this use, but a real, currently-working source: verified with a live, unmocked request before this was documented as working — see PROGRESS.md for the exact result. A direct scrape of `nseindia.com` was tried first and rejected: a plain request to the NSE homepage returns an immediate `403` from a datacenter IP, before ever reaching NSE's own quote API — a genuine dead end, reported rather than built around.

**Locked, non-negotiable properties:**
- **Opt-in, additive, never default.** Gated behind `LIVE_PROVIDER_ENABLED` (default `false`), orthogonal to `DEMO_MODE`/fault injection. `HistoricalReplayProvider` remains the only provider the demo script depends on.
- **Status-only, not scored.** Ticks from this provider are tagged `source="live_delayed_unofficial"` and are reachable only via `GET /provider/live-status` — they are never written to `price_ticks`, never feed baseline computation, and never reach the scoring pipeline. This was an explicit design question, not an assumption: mixing a fragile, occasionally-empty real feed into the same baseline computation the whole scoring engine depends on is a real correctness risk (a bad tick corrupting a rolling baseline) for no demo benefit, given the abstraction point is already fully proven by a real `get_ticks()`/`get_status()` call succeeding or failing honestly. Recommended and implemented this way; revisit only with an explicit decision to do otherwise.
- **No special-casing for its unreliability.** A failed/malformed/empty fetch is not a new error path — `get_status()` reports `UNAVAILABLE` (no successful fetch has ever occurred) or lets `age_seconds` grow past the existing configured thresholds into `STALE`, through the exact same `classify_freshness()` function every other provider uses. No retry/backoff beyond one request per ticker with a 5s timeout.

## Why deterministic scoring, not AI/ML
Explicit rejection of ML-for-novelty. Z-score crossing ±2.0 on rolling 20-30 day return is the primary trigger; volume ratio and sector context are annotations, not folded into a composite weighted score (defensibility in Q&A: one number + plain English beats justifying arbitrary weights). Groww's own AI assistant (GR 1, launched at Groww Next 2026) is positioned as "informative, not autonomous" with explicit consent/execution guardrails — cite this precedent if asked "why no AI": right tool for the job, same principle the host company applies to its own AI.

The *only* acceptable optional LLM use: phrasing the one-line natural-language explanation from an already-computed structured signal (z_score, volume_ratio, sector_relative). Never touches decision logic. Cut first under time pressure — deterministic string template is the default target, not a fallback.

## "Today's Brief" — built, deterministic, not the optional LLM layer above (2026-09-05)

A short (1–3 sentence) synthesis of the current unacknowledged digest signals — "what's happening across everything I need to care about right now," not a repeat of every row. **This is the "deterministic template is the default target" position from the paragraph above, realized one level up**: the per-flag explanation template (`frontend/lib/explain.ts`) synthesizes one flag's structured facts into a sentence; this brief (`backend/app/services/brief.py`) synthesizes the whole active-flag set's structured facts into a couple of sentences. Same principle, same guardrails, one level of aggregation higher.

**Explicitly NOT the optional LLM-phrasing layer described above.** That layer remains separately scoped and still unbuilt — this brief does not use it, is not a preview of it, and does not reduce the case for building it later (if built, it would only ever rephrase the same structured facts this brief already renders deterministically, never add new ones). Keep the two concepts distinct in any Q&A: one is shipped and deterministic; the other is a hypothetical, optional, decision-logic-free phrasing layer that was never built.

**No network call, no external dependency, no timeout/fallback logic anywhere in this feature** — it's pure aggregation over the exact rows `GET /digest` already fetched (total count, counts by severity/sector, the single strongest signal, direction split, sector-wide-vs-stock-specific) followed by fixed string templates. Read-only, computed strictly *after* the digest — it cannot influence severity, ranking, direction, or any scoring/ack-bust logic; nothing here writes to `flags`/`flag_ack`. Zero active signals renders no brief at all — the existing calm empty-state copy is unchanged. Never states a causal reason for a move, never makes a trading/investment claim, never labeled "AI" anywhere in the UI or docs — deterministic template synthesis, full stop.

## `volatility_regime` is computed but not surfaced in the digest — deliberate, not a bug (rationale updated 2026-09-05, decision re-confirmed)

`signal_type = 'volatility_regime'` (stdev_5d/stdev_30d ratio crossing 1.5) is still computed and persisted by the scoring engine exactly as designed — nothing about its computation changed. It was originally hidden from the digest (Phase 5/6) because, under the *original static baselines*, the same handful of tickers crossed the trigger on every single replay cycle with the same generic explanation text — repetitive noise, not a meaningful "something changed" signal.

**That original justification is gone and staying gone.** Rolling, look-ahead-safe baselines (Workstream 1, 2026-09-05) resolved it: a 20-cycle replay run against real seeded data showed the flagged-ticker set genuinely rotating day to day (a `RELIANCE.NS`/`ICICIBANK.NS`/`WIPRO.NS`/`NESTLEIND.NS` cluster for several consecutive days, then a shift to `NTPC.NS`/`POWERGRID.NS`, then `MARUTI.NS`/`ADANIENT.NS`/`ASIANPAINT.NS`). If repetitiveness were still the concern, it would be re-enabled.

**Explicit decision (re-confirmed, not deferred): `volatility_regime` STAYS OUT of the digest for now — a different, current reason, not the stale one.** Two things now built directly on top of "the digest is exclusively `price_zscore`" would need a deliberate adaptation pass first, not a one-line flip:
- **`ORDER BY abs(f.z_score) DESC`** (`app/services/digest.py`) — `volatility_regime` flags have `z_score = NULL`; Postgres sorts `NULL` last under `DESC`, so they'd always land at the bottom regardless of actual severity, not interleaved by genuine statistical unusualness.
- **"Today's Brief"** (`app/services/brief.py`, built 2026-09-05) — `compute_brief_facts()`'s "strongest signal" and "direction" facts are z-score-based; a `NULL` z-score is treated as `0`, which would make a `volatility_regime` flag both silently ineligible to ever be "strongest" and always counted as "up" — never guessed at, but also not a meaningful answer for a signal type that isn't a directional price move in the first place.

Re-enabling `volatility_regime` in the digest is still a good, real future improvement (see README §13) — but it means deciding how these two consumers should treat a non-price-z-score signal (a severity-only ordering fallback? excluding it from the brief's strongest-signal/direction facts specifically?), not just deleting the SQL filter. That's a deliberate next-session decision, not a side effect of an unrelated bug fix.

Resolution (mechanism unchanged): `GET /watchlists/{id}/digest` filters to `signal_type = 'price_zscore'` only (`backend/app/services/digest.py`). No rows are deleted, no scoring logic touched.

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

## In-product brand layer and historical audit log (Workstream 4, 2026-09-05)

Two small, independent product-completeness additions — not a redesign of the digest, not new positioning:

- **Brand identity, in-product only.** A proper wordmark treatment for "signalDigest" and PRODUCT.md's own core-promise tagline (this file's opening line) now appear in the header (`frontend/components/AppHeader.tsx`), plus a small "About this build" dialog (`AboutPanel.tsx`) summarizing what's on this page: what the product does, why it differs from a conventional watchlist, why scoring is deterministic (see above), why "since you last checked" is central (see §"since you last checked" below), and the two Groww engineering posts already cited above. No new positioning was invented, no marketing site or landing page was added, and no investment-advice or live-market-data claims are made — the panel explicitly discloses this build replays real historical data on a clock, not a live feed.
- **Historical changes log.** The `flags` table has always been a durable, queryable audit trail (see DATA_MODEL.md); this workstream exposes it for the first time via `GET /tickers/{ticker}/flags` and a minimal "History" dialog reached per ticker from the watchlist manager — reverse-chronological trading_day/severity/z_score/signal_type, nothing else, no charts or summary stats. Deliberately distinct from the digest: the digest answers "what needs attention now" (current, unacked, watchlist-scoped); history answers "what has this ticker been flagged for" (every record, regardless of ack state or current watchlist membership).
