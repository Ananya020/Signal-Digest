# Data model

```sql
tickers (
  ticker           TEXT PRIMARY KEY,       -- e.g. 'RELIANCE.NS'
  name             TEXT NOT NULL,
  sector           TEXT NOT NULL,          -- hand-curated, small set
  listed_since     DATE
)

price_ticks (
  id               BIGSERIAL PRIMARY KEY,
  ticker           TEXT REFERENCES tickers(ticker),
  price            NUMERIC(12,4) NOT NULL,
  volume           BIGINT,
  ts               TIMESTAMPTZ NOT NULL,
  source           TEXT NOT NULL,          -- real_historical / replay_simulated
  UNIQUE (ticker, ts, source),              -- DB-enforced dedup, not app-layer check-then-insert
  INDEX idx_ticker_ts (ticker, ts DESC)
)

baselines (
  ticker           TEXT REFERENCES tickers(ticker),
  as_of_date       DATE NOT NULL,
  mean_return_30d  NUMERIC(10,6),
  stdev_return_30d NUMERIC(10,6),
  avg_volume_30d   NUMERIC(16,2),
  stdev_5d         NUMERIC(10,6),
  stdev_30d        NUMERIC(10,6),
  sample_size      INT NOT NULL,           -- gates confidence: <20 days -> "not enough history"
  PRIMARY KEY (ticker, as_of_date)
)

flags (
  id               BIGSERIAL PRIMARY KEY,
  ticker           TEXT REFERENCES tickers(ticker),
  trading_day      DATE NOT NULL,
  signal_type      TEXT NOT NULL,          -- 'price_zscore' | 'volatility_regime'
  z_score          NUMERIC(6,3),
  severity         TEXT NOT NULL,          -- notable/significant/extreme (display label)
  severity_rank    SMALLINT NOT NULL,      -- notable=1, significant=2, extreme=3 — comparable
  volume_ratio     NUMERIC(6,2),
  sector_relative  TEXT,                   -- 'sector_wide' | 'stock_specific' | NULL
  computed_at      TIMESTAMPTZ NOT NULL,
  provider_state_at_computation TEXT,      -- audit trail
  UNIQUE (ticker, trading_day, signal_type)
)

watchlists (
  id UUID PRIMARY KEY, user_id UUID NOT NULL, name TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now()
)

watchlist_items (
  watchlist_id UUID REFERENCES watchlists(id),
  ticker TEXT REFERENCES tickers(ticker),
  added_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (watchlist_id, ticker)
)

watchlist_ack_state (
  watchlist_id   UUID REFERENCES watchlists(id) PRIMARY KEY,
  last_seen_hash TEXT NOT NULL,
  last_seen_at   TIMESTAMPTZ NOT NULL
)

flag_ack (
  flag_id               BIGINT REFERENCES flags(id),
  watchlist_id          UUID REFERENCES watchlists(id),
  acked_at              TIMESTAMPTZ NOT NULL,
  severity_rank_at_ack  SMALLINT,               -- Step A (2026-09-06), see below
  z_score_at_ack        NUMERIC(6,3),           -- Step A (2026-09-06), see below
  PRIMARY KEY (flag_id, watchlist_id)
)

-- Step A (2026-09-06), migrations/003_since_last_checked.sql — audit-only,
-- never read by ack-bust logic (flags.py), never affects it. See the
-- "since you last checked" section below.
flag_ack_history (
  id                    BIGSERIAL PRIMARY KEY,
  flag_id               BIGINT REFERENCES flags(id),
  watchlist_id          UUID REFERENCES watchlists(id),
  severity_rank_at_ack  SMALLINT,
  z_score_at_ack        NUMERIC(6,3),
  acked_at              TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ NOT NULL
)

provider_state (
  id INT PRIMARY KEY DEFAULT 1, mode TEXT NOT NULL DEFAULT 'normal', frozen_at TIMESTAMPTZ,
  last_successful_fetch TIMESTAMPTZ,  -- added migrations/002 (Phase 4 correction, see below)
  replay_step INTEGER,  -- added migrations/004 (deployment-prep correction, see below)
  updated_at TIMESTAMPTZ
)
```

**Correction made during Phase 4 implementation (2026-09-04):** `last_successful_fetch` was added after an empirically-verified bug — freshness state depends entirely on `age = now - last_successful_fetch` (`frozen_at` is cosmetic, only used in status `detail`), so the original schema (mode/frozen_at only) meant a process restart during a genuine `stale` fault reset the age clock and incorrectly reported `LIVE` immediately after. `outage` was unaffected (its `UNAVAILABLE` state never consults `age_seconds`). See PROGRESS.md / ARCHITECTURE.md for the fix and verification.

**Correction made during deployment prep (2026-09-06) — second instance of the same bug class, found on the real deployed instance, not locally:** `HistoricalReplayProvider`'s `ReplayClock` (the replay position) was process-memory only, exactly like `last_successful_fetch` before its Phase 4 fix. On Render's free tier, a spin-down/wake (or any restart/redeploy) reset the replay position to the beginning of history — the scheduler silently re-walked from day one, meaning no new flags got scored for ~20+ ticks while `sample_size` re-climbed past the confidence gate, even though previously-computed flags remained correctly stored and unaffected. Fixed the same way: `replay_step` added (`migrations/004_persist_replay_step.sql`), persisted via the same UPSERT as `mode`/`frozen_at`/`last_successful_fetch`, hydrated at startup by `FaultInjectingProvider.sync_from_db()` (resets `wrapped.clock` to the persisted value) and written every scheduler tick by `persist()`. Freeze semantics (`'stale'` no-ops `advance()`) are unaffected — this only changes what happens at startup. Verified empirically with a real hard-kill (`SIGKILL`, not graceful shutdown) against a running instance: replay resumed from the persisted step, not from zero. See PROGRESS.md.

## Why each table exists
- `price_ticks` — immutable source of truth, needed to recompute anything after fault-recovery.
- `baselines` — precomputed ahead of scoring, not derived per-request (the "rebuild on every read" anti-pattern Groww's own Holdings post is about). **Workstream 1 (2026-09-05):** genuinely per-day now — one row per `(ticker, as_of_date)`, recomputed once per scheduler cycle from only the days strictly before `as_of_date` (look-ahead-safe), inserted as a new row rather than overwritten. See `backend/app/data/baselines.py::compute_baseline_as_of` / `load_baseline_as_of`. `load_latest_baseline` still exists for "whatever's most recently computed, regardless of day" use cases (the Phase 1 seed script, ad-hoc scripts) — scoring and evidence must use the per-day functions, never this one.
- `flags` — durable record of *why* something was surfaced; required for the evidence endpoint and the uniqueness constraint that prevents duplicate flags.
- `flag_ack` / `watchlist_ack_state` split deliberately: aggregate hash = cheap ETag-style short-circuit; per-flag table = fine-grained truth for "which specific things are new."

## CRITICAL: severity-escalation must bust the ack
`flags` upserts on `(ticker, trading_day, signal_type)`; `flag_ack` keys on the constant `flag_id`. Without this fix, a flag that escalates from "notable" to "extreme" intraday stays silently acked even though it's a genuinely new qualifying event.

**Correction made during Phase 2 implementation (2026-09-04) — the original SQL below is superseded.** The original design put a `WHERE EXCLUDED.severity_rank IS DISTINCT FROM flags.severity_rank OR flags.severity_rank IS NULL` clause directly on the `ON CONFLICT DO UPDATE`. Verified directly against real Postgres: when that `WHERE` evaluates false, `RETURNING` yields **zero rows** — the `UPDATE` doesn't run at all, on any column. That clause was conflating two different questions — "should the flag's evidence be refreshed?" and "should the ack be busted?" — under one condition. Consequence: a same-severity rerun (e.g. `z_score` moving from 2.1 to 2.4, still `notable`) silently skipped updating `z_score`, `volume_ratio`, `sector_relative`, `computed_at`, and `provider_state_at_computation` — the flag went stale even though a newer computation had just run. Caught by a dedicated regression test in `backend/tests/test_flags_ack_bust.py` before this ever reached production behavior.

**Corrected upsert (one transaction, still both steps — implemented in `backend/app/services/flags.py`):**
```sql
-- previous severity_rank is read BEFORE this statement, in the same transaction
INSERT INTO flags (ticker, trading_day, signal_type, z_score, severity, severity_rank, volume_ratio, sector_relative, computed_at, provider_state_at_computation)
VALUES (...)
ON CONFLICT (ticker, trading_day, signal_type) DO UPDATE
SET z_score = EXCLUDED.z_score, severity = EXCLUDED.severity,
    severity_rank = EXCLUDED.severity_rank, volume_ratio = EXCLUDED.volume_ratio,
    sector_relative = EXCLUDED.sector_relative, computed_at = EXCLUDED.computed_at,
    provider_state_at_computation = EXCLUDED.provider_state_at_computation
-- no WHERE clause: evidence always refreshes to the latest computation, unconditionally
RETURNING id, severity_rank, (xmax = 0) AS was_insert;
```
```python
# app-layer, same transaction as the upsert above:
if not was_insert and new_severity_rank > previous_severity_rank:
    DELETE FROM flag_ack WHERE flag_id = :flag_id
# equal or lower rank -> leave flag_ack untouched, no-op — decided independently
# of whether the evidence columns were refreshed above.
```

This preserves the intended ack-bust semantics exactly (escalation busts, de-escalation and equal-rank don't) while fixing the stale-evidence defect. The upsert and the conditional delete remain one atomic transaction — never split across two.

**Deliberate, asymmetric by design (state this in the README):** severity escalation busts the ack; de-escalation does not. An ack means "user has seen and dismissed this level of concern." Worse-than-dismissed is new information and must resurface. Better-than-dismissed has no new concern to raise — staying acked is correct, not an oversight.

No API/query shape change needed — the existing "unacked flags" query in `GET /digest` picks up a resurfaced escalated flag for free once it no longer has a `flag_ack` row.

## Key query — "what's changed since last check"
```sql
SELECT f.* FROM flags f
JOIN watchlist_items wi ON wi.ticker = f.ticker
LEFT JOIN flag_ack fa ON fa.flag_id = f.id AND fa.watchlist_id = wi.watchlist_id
WHERE wi.watchlist_id = :wid AND fa.flag_id IS NULL
ORDER BY f.z_score DESC;
```
At real scale, short-circuit first: compare `watchlist_ack_state.last_seen_hash` against a freshly computed aggregate hash — if equal, skip this join entirely (the 304-equivalent).

## "Since you last checked" (Step A, 2026-09-06) — implementation, locked

`flag_ack` snapshots `severity_rank`/`z_score` at the moment of ack (`POST /ack`). When escalation later busts that ack, `flags.py::upsert_flag_with_ack_bust` copies the live `flag_ack` row into `flag_ack_history` (`superseded_at = now()`) **immediately before** the existing `DELETE FROM flag_ack` — same transaction, delete's condition/timing/boundary unchanged. De-escalation and equal-rank reruns write nothing here (nothing was superseded).

`GET /digest`'s `since_last_ack` per flag: the live `flag_ack` row if currently acked, else the most recent `flag_ack_history` row if previously acked and since busted, else `null` (never fabricated) — see `app/services/digest.py::load_since_last_ack`. Read-only, computed after the digest query; cannot influence scoring, ranking, or the ETag hash.

**Known integrity gap, not yet closed:** `flag_ack_history.flag_id`/`watchlist_id` have no `ON DELETE CASCADE`, and today's app never deletes a `flags` or `watchlists` row (the only delete endpoint, `DELETE /watchlists/{id}/items/{ticker}`, only touches `watchlist_items`), so no orphan currently exists. A future watchlist-delete or flag-purge feature must explicitly clear `flag_ack_history` first (same pattern `flag_ack` cleanup already needs) or it will leave orphaned rows in what is meant to be a trustworthy audit trail.

## Data exclusions — a real corporate-action artifact, found and excluded (2026-09-06)

Investigating why the digest showed several unrelated-sector tickers simultaneously EXTREME (a real anomaly report, not hypothetical), a direct data check found two absurd `price_zscore` outliers with no counterpart anywhere else in the dataset: `TRENT.NS` at `z=-26.485` and `ITC.NS` at `z=-17.713`, both on `2026-01-01` — every other extreme flag across the full seeded history falls in the `|z| 3.5-7.4` range.

**Root cause, confirmed empirically, not assumed:**
- `TRENT.NS`: -33.05% single-day move (4272.69 → 2860.71) with *below-average* volume (0.72x the trailing 20-day average).
- `ITC.NS`: -9.71% single-day move (384.26 → 346.93) with a *34.1x* volume spike.
- A live yfinance re-fetch on 2026-09-06 reproduced both numbers exactly, in both `auto_adjust=True` and `auto_adjust=False`'s `Adj Close` column — ruling out an ingestion-field bug (`seed_historical_data.py` already used `auto_adjust=True`; re-ingesting would change nothing).
- Neither ticker has a recorded split or dividend near that date in yfinance's own actions API — expected, not exculpatory, since that API only tracks plain splits/dividends, never demergers, bonus issues, or schemes of arrangement.
- Conclusion: both are genuine, correctly-reflected corporate-action price resets (TRENT.NS's pattern — large move, no volume — is consistent with a bonus issue/scheme of arrangement; ITC.NS's pattern — large move + volume spike — is the textbook signature of a demerger/spin-off adjustment), not organic trading volatility and not a data-ingestion defect.

**Fix**: `app/data/exclusions.py` — a documented, git-reviewable constant (`KNOWN_EXCLUSIONS: list[DataExclusion]`, each with a `ticker`/`excluded_date`/`reason`), read by `app/data/baselines.py::compute_baseline_from_series` before any of `stdev_return_30d`/`stdev_30d`/`stdev_5d`/`mean_return_30d` is computed. A documented constant was chosen over a new `data_exclusions` DB table specifically because this fix must eventually also apply to the already-seeded remote deployment (a separate follow-up) — a code constant needs no migration/backfill step to take effect there, while staying just as auditable via git blame.

The underlying `price_ticks` row for the excluded date is **never** modified or deleted — it genuinely is what the ticker traded at. Only the single daily return *attributed to* that date is excluded from every rolling window that would otherwise include it.

**Window-shifting decision (deliberately chosen, verified empirically — not incidental):** with real seeded data, excluding a return does **not** shrink `sample_size` to 29 for the ~30 trading days after the excluded date — it stays at a full 30, because the window reaches one extra real trading day further back to compensate, and both tickers have ample prior history to reach into (confirmed: `sample_size` measured 30 → 30 across the entire affected window in both directions, before and after the fix). This is a deliberate choice, justified by treating an excluded date exactly like a pre-existing calendar gap (a weekend, a holiday) — this codebase's rolling window has never been "the last 30 calendar days," it has always been "the last 30 valid trading-day returns." Reusing one more already-real, already-observed trading day is not fabrication (unlike, say, inventing a synthetic 31st value) — `sample_size` only drops below 30 near the very start of a ticker's available history, where there is no 31st real day to reach back into, exactly mirroring the existing `MIN_SAMPLE_SIZE` honesty principle. Both behaviors (extend-back with ample history, shrink-to-29 without it) are pinned down by dedicated unit tests (`test_baselines.py`).

**What changed after recomputation** (`backend/scripts/recompute_after_exclusion.py`, run once locally against the real seeded data — not yet applied to the remote deployment): `stdev_return_30d` for the ~30-trading-day window after 2026-01-01 dropped from an implausible ~6.2%/day (TRENT.NS) and ~1.9%/day (ITC.NS) to a plausible ~1.2-2.5%/day and ~0.5-1.5%/day respectively. This did not just remove false extremes — it also **revealed previously-suppressed genuine large moves**: `TRENT.NS` 2026-01-06 (`z=-6.49`, now extreme) and `ITC.NS` 2026-01-02 (`z=-6.89`, now extreme) and 2026-02-06 (`z=4.68`, now extreme, ack-bust correctly fired since that flag had been previously acked at a lower severity) had all been invisible or under-scored before the fix, because the artifact's inflated `stdev_return_30d` was diluting every real move's z-score in that window, not just manufacturing false positives. The `2026-01-01` flags themselves (`z=-17.713`/`z=-26.485`) are **unchanged** by this fix — they're generated by comparing that day's own return against a PRIOR baseline that (by the existing look-ahead-safe design) never includes that day's own return anyway, so the contamination there is the test value itself, not a baseline-window contamination; whether to also suppress/relabel those two specific flags is an explicit open follow-up, not silently done here.

## Event Grouping (Step B, 2026-09-06) — no schema change, read-time only

`compute_events()` (`app/services/digest.py`) is a pure function over the exact rows `_UNACKED_FLAGS_SQL` already returns for a `GET /digest` call — no new table, no persistence, no new invalidation logic, recomputed fresh on every request from data already fetched. It groups `sector_relative = 'sector_wide'` rows by `sector`, keeping only clusters with 2+ members (a lone sector-wide flag is not an "event" — it renders as an ordinary row). `sector_relative = 'stock_specific'` rows are never grouped. Output: `events: [{sector, tickers, strongest_z_score}]`, sorted strongest-first. Ack semantics are completely untouched — each member is still acked individually through the existing `POST /ack`, keyed by its own `flag_id` exactly as before; there is no bulk-ack-by-event anywhere in the model.
