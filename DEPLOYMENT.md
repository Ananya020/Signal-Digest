# Deployment runbook — Render (backend + Postgres) + Vercel (frontend)

This is a manual runbook for a real deployment. It was written and verified
(Dockerfile build, local docker-compose smoke test, backend test suite) from
a sandbox with **no network access to Render or Vercel** — nothing here was
or could be executed against those platforms. Every step below is something
you perform by hand on their dashboards or your own machine's CLI.

Read alongside: `.env.example` (every variable's authoritative description),
`ARCHITECTURE.md` (system diagram, freshness thresholds), `RELIABILITY.md`
(security review section).

---

## 0. Before you start

- A GitHub repo containing this project, pushed and up to date.
- A Render account (https://render.com), a Vercel account (https://vercel.com) — both support signing in with GitHub directly, which also grants the repo-connection permission you'll need in steps 1 and 6.
- Nothing here provisions credit-card-billed resources beyond Render's free/starter Postgres and web service tiers unless you explicitly pick a paid plan on their dashboard.

---

## 1. Provision Postgres on Render

1. Render dashboard → **New** → **PostgreSQL**.
2. Name it (e.g. `signaldigest-db`), pick a region close to where you'll put the backend web service (Render charges cross-region traffic and adds latency if they differ).
3. Plan: the free tier is fine for a demo/submission; note that Render's free Postgres instances expire after 30 days and are **not** recommended for anything you need to keep running past that window.
4. Create it, then wait for status **Available**.
5. Open the database's page → copy the **External Database URL** (not the internal one — you need external access for the migration/seed step below, run from your own machine, not from inside Render's network). It looks like:
   ```
   postgresql://<user>:<password>@<host>.render.com/<dbname>?sslmode=require
   ```
   Keep this value private — treat it exactly like a real production secret; you'll paste it into `DATABASE_URL` in two places (your local shell for migrations/seed, and the backend web service's env vars in step 3).

---

## 2. Run migrations + seed against the remote DB

Do this from your own machine (this repo checked out locally), **not** via `docker compose exec` — Postgres is remote now, there is no local container to exec into. `psql` and Python with this repo's venv are the only requirements.

### 2a. Apply migrations, in order, exactly as numbered

```bash
# from the repo root
psql "<the External Database URL from step 1>" -f backend/migrations/001_init.sql
psql "<the External Database URL from step 1>" -f backend/migrations/002_add_last_successful_fetch.sql
psql "<the External Database URL from step 1>" -f backend/migrations/003_since_last_checked.sql
```

Run them in that exact numeric order — `002` adds a column `003`'s tables don't depend on, but there is no migration-tracking mechanism in this project (per CLAUDE.md: no migration tool, numbered files applied manually via `psql -f`), so nothing enforces the order for you. If a fourth migration exists by the time you deploy, check `backend/migrations/` for the actual current file list before running these commands — this runbook can go stale.

Each file is idempotent-safe to inspect but **not** safe to blindly re-run (they're plain `CREATE TABLE`/`ALTER TABLE`, no `IF NOT EXISTS` guards) — if a run partially fails, read the error before retrying rather than re-running the whole file.

### 2b. Seed real historical data

The seed script reads `DATABASE_URL` via this repo's own `pydantic-settings` config (`backend/app/config.py`), the same as the running app — so point your **local** `.env` at the remote DB temporarily, or export it inline for the one command:

```bash
cd backend
DATABASE_URL="<the External Database URL from step 1>" JWT_SECRET="placeholder-not-used-by-this-script" python -m scripts.seed_historical_data
```

This is a one-off manual backfill (`backend/scripts/seed_historical_data.py`) — pulls ~1 year of real daily OHLCV via `yfinance` for the fixed ~35-ticker universe, stores it, computes one baseline row per ticker. It runs for real, so expect it to take a few minutes (yfinance rate-limits real requests) — it's safe to re-run if interrupted (upserts on the real unique constraints, per the script's own docstring).

**Do not run `seed_demo_escalation_precondition.py` or `reset_demo_state.py` against production data unless you specifically want to** — both are demo-rehearsal tools that mutate flag/ack state; they're fine to run again pre-demo, but running them against a real user's data would be destructive to genuine history.

### 2c. Spot-check before moving on

```bash
psql "<the External Database URL>" -c "SELECT count(*) FROM tickers;"     # expect ~34-35
psql "<the External Database URL>" -c "SELECT count(*) FROM price_ticks;" # expect several thousand
psql "<the External Database URL>" -c "SELECT count(*) FROM baselines;"   # one per successfully-seeded ticker
```

---

## 3. Deploy the backend to Render

1. Render dashboard → **New** → **Web Service** → connect your GitHub account (if not already) → select this repo.
2. **Root directory**: `backend` (the Dockerfile added by this session lives at `backend/Dockerfile`).
3. **Runtime**: Docker (Render auto-detects the Dockerfile once you point it at that root directory — don't pick "Python" runtime and a build/start command instead, since the Dockerfile is the source of truth for how this app starts, including the `$PORT` binding).
4. **Region**: same region you picked for Postgres in step 1.
5. **Instance type**: your choice; the free tier spins down on inactivity, which means the APScheduler background job (and thus the replay clock / flag generation) also stops while spun down — fine for an on-demand demo, not for something meant to run continuously.
6. **Environment variables** — set every one of these (values/descriptions pulled directly from `.env.example`):

   | Variable | Value for this deployment | What it does |
   |---|---|---|
   | `DATABASE_URL` | the **Internal** Database URL from Render's Postgres page (not the External one you used for migrations — the backend runs inside Render's network, so use the faster/free internal route) | asyncpg connection string; `?sslmode=require` should already be present if Render includes it in the URL it gives you — if not, append it yourself, since a remote managed Postgres requires TLS |
   | `JWT_SECRET` | a real random value you generate (e.g. `openssl rand -hex 32`) — never the placeholder in `.env.example` | signing seam for the demo-user identity dependency (`app/auth.py`); not yet used for real JWT verification (see ARCHITECTURE.md), but must still be a real secret, not committed anywhere |
   | `DEMO_MODE` | `true` (unless you specifically want `/admin/fault` disabled for this deployment) | gates `POST /admin/fault` — 404s unconditionally when unset, per RELIABILITY.md's security review |
   | `FRONTEND_ORIGIN` | the exact Vercel URL you'll get in step 6, e.g. `https://signaldigest.vercel.app` (no trailing slash) — you'll come back and set this precisely once Vercel gives you the real URL | CORS `allow_origins` — must be the real deployed frontend origin, never `*` |
   | `DEMO_SECRET` | (optional) a real random value, e.g. `openssl rand -hex 24` — leave **unset** if you want `/admin/fault` to behave exactly as `DEMO_MODE` already gates it | deployment-only hardening added this session (see §7 below) — additive to `DEMO_MODE`, not a replacement |
   | `FRESHNESS_LIVE_SECONDS` / `FRESHNESS_RECENT_SECONDS` / `FRESHNESS_DELAYED_SECONDS` / `FRESHNESS_STALE_SECONDS` | `5` / `15` / `30` / `30` (demo-compressed defaults) — or the minutes-scale figures from ARCHITECTURE.md's table if you want production-realistic thresholds instead | freshness-state thresholds; no hardcoded values exist in the freshness code, everything reads these |
   | `SCHEDULER_INTERVAL_SECONDS` | `5` | how often the background scoring tick runs |
   | `LIVE_PROVIDER_ENABLED` | `false` (leave off unless you specifically want the optional unofficial live-delayed NSE provider reachable via `/provider/live-status`) | Workstream 3's opt-in second provider — never affects scoring/baselines even when on |

7. Deploy. Watch the build logs — should mirror this session's local `docker build` verification (pip install, then the app starts and logs `Application startup complete.`).
8. Once live, confirm `/health`:
   ```bash
   curl https://<your-render-service>.onrender.com/health
   # expect: {"status":"ok"}
   ```
   This does a real `SELECT 1` round-trip against Postgres (`backend/app/routers/health.py`) — a genuine DB outage will make this genuinely fail, not just report a cached "ok," so Render's health-check-based auto-restart logic will behave correctly if the app truly goes unhealthy. If you configure a Render health check path, point it at `/health`.


## 4. Deploy the frontend to Vercel

1. Vercel dashboard → **Add New** → **Project** → import this repo from GitHub.
2. **Root directory**: `frontend`.
3. Framework preset: Next.js (Vercel auto-detects this).
4. **Environment variables**:

   | Variable | Value | What it does |
   |---|---|---|
   | `NEXT_PUBLIC_API_URL` | your Render backend's real URL, e.g. `https://signaldigest-backend.onrender.com` (no trailing slash) | the frontend's API base URL (`frontend/lib/api.ts`) — defaults to `http://localhost:8000` when unset, which is why this **must** be set explicitly for a deployed build |

5. Deploy. Vercel gives you a real URL (e.g. `https://signaldigest.vercel.app` or a project-specific subdomain).

---

## 5. Close the loop: point the backend's CORS at the real frontend URL

Go back to the Render backend's environment variables and set `FRONTEND_ORIGIN` to the **exact** URL Vercel just gave you (step 4's result) — protocol, host, no trailing slash, no path. Save — Render will redeploy the service automatically on an env var change.

**Why this order (Postgres → migrate/seed → backend → confirm `/health` → frontend → CORS) and not some other order:** the backend needs a working DB before it can start `run_scoring_cycle` on its first scheduler tick, and the frontend's build doesn't need the backend to be reachable to build correctly (it's a client-side fetch at runtime, not a build-time dependency) — but you can't get the *real* frontend URL to put into `FRONTEND_ORIGIN` until after the frontend is deployed once, which is why this is a two-pass step, not a single upfront CORS config.

---

## 6. Confirm CORS end-to-end

Open the real deployed frontend URL in a browser, open devtools → Network tab, and confirm:
- The dashboard loads real data (not stuck on a loading skeleton) — a CORS failure shows up as a failed/blocked request to the backend origin, visible in the Network tab and usually logged to the console as a CORS error.
- `GET /watchlists`, `GET /digest`, etc. all succeed with real 200s from the Render URL, not the `localhost:8000` default (confirms `NEXT_PUBLIC_API_URL` actually took effect at build/runtime).

If CORS fails: the most common cause is a mismatch between the exact string in `FRONTEND_ORIGIN` and the browser's actual origin header (e.g. `https://` vs missing scheme, or a trailing slash) — `CORSMiddleware`'s `allow_origins` list does exact string matching, not a pattern match.

---

## 7. `/admin/fault` deployment hardening — what changed and why

This session added a second, additive gate to `POST /admin/fault`, on top of the existing `DEMO_MODE` check (`backend/app/routers/admin.py`):

- If `DEMO_SECRET` is **unset** (the default — matches `.env.example`, matches local dev, matches every environment before this change existed): the endpoint behaves **exactly as it always has**. Only `DEMO_MODE` is checked. Nothing about local dev changes.
- If `DEMO_SECRET` **is** set (intended only for a public deployment where you don't want an anonymous internet visitor flipping fault-injection state on your live demo): the caller must also send the exact same value back, via either the `X-Demo-Secret` header or a `demo_secret` query param. A missing or wrong value 404s — identically to how the `DEMO_MODE` gate already fails — so a public deployment can't be probed to tell "wrong secret" apart from "this route doesn't exist."

**Recommendation implemented (per the two options this session was asked to choose between): unset disables the extra check entirely, rather than requiring an explicit dev value.** Reasoning: this project already has exactly one such secret-gated pattern (`DEMO_MODE` itself) that behaves this way — unset means off, not "unset means you forgot to configure it correctly." Requiring every local dev environment to also set a placeholder `DEMO_SECRET` would add friction to local dev for a check that only matters once the endpoint is reachable from the public internet, which is precisely the condition Render deployment (and not local dev) introduces.

If you want `/admin/fault` protected on the live deployment: set `DEMO_SECRET` in Render's environment variables (step 3, table above) to a real random value, and update `frontend/components/FaultControl.tsx`'s call site to send it — **not done in this session**, since the frontend demo-control UI wiring wasn't in scope here and doing it without seeing the deployed URL/secret flow live would be guessing at the UX; flagging as a follow-up if you want the live fault-injection demo button to keep working against a `DEMO_SECRET`-protected deployment.

---

## 8. Non-goals of this session (explicit)

- Nothing was actually deployed — this sandbox has no network access to Render or Vercel. Every step above is manual, for you to execute.
- No scoring, reliability, or core application logic changed.
- The existing `DEMO_MODE` gate was not weakened — `DEMO_SECRET` is purely additive (see §7); with it unset, behavior is byte-for-byte identical to before this session.
