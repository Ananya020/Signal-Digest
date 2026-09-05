/**
 * Automated end-to-end demo rehearsal.
 *
 * Encodes the canonical Stage 5 demo script (PROGRESS.md's "Canonical demo
 * script" section) step for step, against a REAL running backend, REAL
 * Postgres, and the REAL frontend — no mocks. Its purpose is to make
 * demo-readiness verifiable by running one command, not just by a human
 * rehearsing it.
 *
 * Prerequisites (see README.md's "E2E demo rehearsal" section):
 *   - `docker compose up -d postgres` from the repo root
 *   - real seeded data present (backend/scripts/seed_historical_data.py,
 *     already run for this repo)
 *
 * Everything else (backend, frontend) is started by Playwright's `webServer`
 * config if not already running — see playwright.config.ts.
 */

import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import { expect, type Locator, type Page, test } from "@playwright/test";

const execFileAsync = promisify(execFile);

const BACKEND_URL = "http://localhost:8000";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.PYTHON_BIN ?? "python";

// The escalation-flip beat waits on the REAL scheduler to reach a specific
// future trading day. Bounded, not indefinite — see the wait step below for
// why this number and what a more robust condition would look like.
const ESCALATION_WAIT_TIMEOUT_MS = 150_000;

interface EscalationCandidate {
  ticker: string;
  trading_day: string;
  z: number;
  severity: string;
  severity_rank: number;
  step: number;
}

async function runPythonModule(args: string[]): Promise<string> {
  const { stdout } = await execFileAsync(PYTHON, ["-m", ...args], { cwd: BACKEND_DIR });
  return stdout;
}

async function api(pathname: string, init?: RequestInit) {
  const res = await fetch(`${BACKEND_URL}${pathname}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${init?.method ?? "GET"} ${pathname} -> ${res.status}: ${body}`);
  }
  return res.status === 204 ? null : res.json();
}

/** `/provider/status`'s `detail` field is a plain string like
 * "mode=normal, replay step 42" — the only place the live replay step is
 * observable externally (it's in-memory only, never persisted as a number). */
function parseReplayStep(detail: string): number {
  const match = detail.match(/replay step (\d+)/);
  if (!match) throw new Error(`Could not parse replay step from provider status detail: "${detail}"`);
  return Number(match[1]);
}

/** The frontend's own bootstrap (`lib/bootstrap.ts::ensureBootstrapWatchlist`)
 * always attaches to the FIRST watchlist `GET /watchlists` returns (creating
 * one only if that list is empty) — it has no way to pick a specific one. So
 * this test MUST target that same first watchlist for the browser to ever
 * show what it sets up; a separate, isolated watchlist would be invisible in
 * the UI. Side effects on it (tickers added) are tracked and reverted in
 * `afterAll` instead — see `addedTickers` below. */
async function ensureWatchlistId(): Promise<string> {
  const existing = (await api("/watchlists")) as Array<{ id: string }>;
  if (existing.length > 0) return existing[0].id;
  const created = (await api("/watchlists", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "E2E Rehearsal Watchlist" }),
  })) as { id: string };
  return created.id;
}

/** The digest deliberately buffers background updates behind a "Show N new
 * signal(s)" affordance (page.tsx's viewed-vs-latest split, Stage 2 design)
 * — a poll revealing the escalated flag does NOT auto-render it. This polls
 * for `target` to appear, clicking that affordance whenever it's present,
 * until `target` shows up or `timeoutMs` elapses. Not a single fixed sleep:
 * the real scheduler's pace is what's being waited on, so this re-checks
 * and re-clicks on a short fixed interval instead of guessing one delay. */
async function waitByPullingInNewSignals(page: Page, target: Locator, timeoutMs: number): Promise<void> {
  const pullIn = page.getByRole("button", { name: "Review new signals" });
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await target.isVisible().catch(() => false)) return;
    if (await pullIn.isVisible().catch(() => false)) {
      await pullIn.click().catch(() => {});
    }
    await page.waitForTimeout(2_000);
  }
  throw new Error(
    `Timed out after ${timeoutMs}ms waiting for the escalated flag to appear, even while repeatedly ` +
      "pulling in new signals. Either the live scheduler hasn't reached the target trading day yet " +
      "(see the timeout note in the test), or the escalation genuinely didn't fire."
  );
}

/** Both the watchlist-manager list and the digest list render an `<li>`
 * containing the bare ticker text (e.g. "TATASTEEL (Energy/Materials)" vs.
 * a digest row) — a plain `page.locator("li", { hasText })` ambiguously
 * matches whichever renders first in the DOM (the watchlist list, above the
 * digest). Digest rows are the only `<li>`s with an Acknowledge button, so
 * that's the disambiguator. */
function digestRow(page: Page, bareTicker: string): Locator {
  return page
    .locator("li")
    .filter({ hasText: bareTicker })
    .filter({ has: page.getByRole("button", { name: "Acknowledge" }) })
    .first();
}

async function ensureTickerInWatchlist(watchlistId: string, ticker: string): Promise<void> {
  await api(`/watchlists/${watchlistId}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker }),
  });
}

test.describe.configure({ mode: "serial" }); // one continuous rehearsal, later steps depend on earlier state

let watchlistId: string;
let ackTicker: string; // a ticker with an early, real, pre-populated flag — used for the ack/evidence steps
let escalation: EscalationCandidate;
let preExistingTickers: Set<string>; // watchlist membership as found — anything this test adds beyond this gets removed in afterAll

test.beforeAll(async () => {
  // Fail fast with a clear message rather than a mysterious later timeout:
  // the fault-injection control only renders when demo_mode is true.
  const initialStatus = (await api("/provider/status")) as { demo_mode: boolean };
  if (!initialStatus.demo_mode) {
    throw new Error(
      "Backend is running with DEMO_MODE unset/false — the fault-injection control this rehearsal " +
        "depends on won't render. Set DEMO_MODE=true in backend/.env (already the repo default) and " +
        "restart the backend."
    );
  }

  // --- Step 1 setup: fresh demo state -------------------------------------
  // Real script, real DB truncation — not a mock. Leaves real seeded
  // price_ticks/baselines/watchlists untouched (see the script's own
  // docstring / PROGRESS.md).
  await runPythonModule(["scripts.reset_demo_state"]);

  watchlistId = await ensureWatchlistId();
  const preExistingItems = (await api(`/watchlists/${watchlistId}/items`)) as Array<{ ticker: string }>;
  preExistingTickers = new Set(preExistingItems.map((i) => i.ticker));

  // A ticker guaranteed to produce a real flag at the earliest possible
  // replay step (MIN_SAMPLE_SIZE=20 gates anything before step 20 for ANY
  // ticker — TATASTEEL.NS crosses "extreme" at exactly step 20 against the
  // real seeded history, independently confirmed via
  // scripts.find_escalation_candidate during this test's development).
  ackTicker = "TATASTEEL.NS";
  await ensureTickerInWatchlist(watchlistId, ackTicker);

  // Fast-forward REAL scoring (the exact function the live scheduler calls)
  // synchronously, using a throwaway provider instance independent of the
  // live server's own in-memory replay clock — this only pre-populates real
  // flag rows in the DB so step 2 below doesn't have to wait on wall-clock
  // scheduler ticks for the FIRST flag to appear. It does not affect where
  // the live server's own clock is (checked separately below).
  await runPythonModule(["scripts.run_scoring_once", "--ticks", "25", "--start-step", "1"]);

  // --- Escalation-flip target: found dynamically, not hardcoded -----------
  // The live server's clock position is unknown ahead of time (it may
  // already be running from an earlier session) — ask it directly.
  const statusBeforeSeed = (await api("/provider/status")) as { detail: string };
  const currentStep = parseReplayStep(statusBeforeSeed.detail);

  const candidateJson = await runPythonModule([
    "scripts.find_escalation_candidate",
    "--min-step",
    String(currentStep),
    "--min-severity-rank",
    "3", // extreme — makes the Today's Brief "extreme-severity" clause assertion meaningful
  ]);
  const candidate = JSON.parse(candidateJson.trim()) as EscalationCandidate | null;
  if (!candidate) {
    throw new Error(
      `No real extreme-severity escalation candidate found beyond replay step ${currentStep}. ` +
        "This would mean the live server's replay position has advanced past all real qualifying " +
        "days in the seeded history — restart the backend (resets its in-memory clock to step 1) and re-run."
    );
  }
  escalation = candidate;

  await ensureTickerInWatchlist(watchlistId, escalation.ticker);

  // Seed the real, unmodified precondition script — it independently
  // re-verifies the same outcome (defense in depth: two separate
  // computations, both against the real unmodified scoring functions,
  // must agree) and refuses to seed if the placeholder wouldn't actually
  // be superseded.
  await runPythonModule([
    "scripts.seed_demo_escalation_precondition",
    "--ticker",
    escalation.ticker,
    "--trading-day",
    escalation.trading_day,
    "--watchlist-id",
    watchlistId,
    "--placeholder-severity",
    "notable",
  ]);
});

test.afterAll(async () => {
  // This test targets whatever watchlist the frontend's own bootstrap
  // already uses (see ensureWatchlistId's doc comment) — a real watchlist a
  // human may also be using for manual rehearsals, not a disposable fixture.
  // Restore its membership to exactly what it was before this run, same
  // spirit as reset_demo_state.py leaving real seeded data untouched.
  for (const ticker of [ackTicker, escalation?.ticker]) {
    if (ticker && !preExistingTickers.has(ticker)) {
      await api(`/watchlists/${watchlistId}/items/${ticker}`, { method: "DELETE" }).catch(() => {});
    }
  }
});

test("full demo rehearsal: fresh load -> evidence -> ack -> fault injection -> escalation-flip -> brief", async ({
  page,
}) => {
  // --- Step 1: fresh load, real flags, LIVE freshness ---------------------
  await page.goto("/");

  await expect(page.getByText("Live", { exact: true })).toBeVisible({ timeout: 30_000 });

  const ackRow = digestRow(page, ackTicker.replace(".NS", ""));
  await expect(ackRow).toBeVisible({ timeout: 30_000 });
  // A real z-score is rendered inline (e.g. "4.6σ") — not placeholder text.
  await expect(ackRow.getByText(/\d+\.\dσ/)).toBeVisible();

  // --- Step 2: "show your work" — real evidence data -----------------------
  await ackRow.getByText(ackTicker.replace(".NS", "")).click();
  const evidenceDialog = page.getByRole("img", { name: /Distribution of daily returns/ });
  await expect(evidenceDialog).toBeVisible({ timeout: 10_000 });
  // The stats row renders real computed numbers, never "N/A" for a flag
  // that has a real z-score.
  const zStat = page.locator("div", { has: page.getByText("Z-score", { exact: true }) }).first();
  await expect(zStat.getByText(/^-?\d+\.\d+$/)).toBeVisible();
  const meanStat = page.locator("div", { has: page.getByText("Historical mean", { exact: true }) }).first();
  await expect(meanStat.getByText(/^-?\d+\.\d+%$/)).toBeVisible();
  await page.getByLabel("Close").click();

  // --- Step 3: acknowledge — disappears from the unacked view -------------
  // Dwell delay (ACK_DWELL_MS) must elapse before the button is enabled.
  const ackButton = ackRow.getByRole("button", { name: "Acknowledge" });
  await expect(ackButton).toBeEnabled({ timeout: 5_000 });
  await ackButton.click();
  await expect(ackRow).toBeHidden({ timeout: 10_000 });

  // --- Step 4: fault injection — outage then recover -----------------------
  await page.getByRole("button", { name: "Outage" }).click();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "Recover" }).click();
  // Not instant by design — freshness only returns to LIVE once the next
  // real scheduler tick actually re-fetches (see fault_injecting.py's
  // documented 'recover' semantics). Bounded to a couple of scheduler
  // intervals + the LIVE threshold.
  await expect(page.getByText("Live", { exact: true })).toBeVisible({ timeout: 30_000 });

  // --- Step 5: combined beat — the escalation-flip, waited for for real ----
  const escalatedBareTicker = escalation.ticker.replace(".NS", "");
  const escalatedRow = digestRow(page, escalatedBareTicker);

  // Bounded, not indefinite: the live scheduler must independently advance
  // real wall-clock ticks from wherever its clock is to `escalation.step`.
  // SCHEDULER_INTERVAL_SECONDS=2 (set in playwright.config.ts) when
  // Playwright starts the backend itself, but a REUSED pre-existing server
  // may be running the slower 5s default — 150s comfortably covers a
  // worst-case gap of dozens of steps at either interval. Also polls and
  // clicks the "Show N new signals" pull-in affordance, since a background
  // poll revealing the escalated flag does not auto-render it (see
  // waitByPullingInNewSignals's own doc comment for why a fixed sleep here
  // would be the wrong tool).
  await waitByPullingInNewSignals(page, escalatedRow, ESCALATION_WAIT_TIMEOUT_MS);
  await expect(escalatedRow.getByText(/extreme/i)).toBeVisible();

  // Verify the ACTUAL observed value against what find_escalation_candidate
  // independently pre-computed — not just "some flag appeared unacked."
  const zText = await escalatedRow.getByText(/\d+\.\dσ/).first().textContent();
  const observedZ = Number(zText?.match(/(\d+\.\d)σ/)?.[1]);
  expect(observedZ).toBeCloseTo(Math.abs(escalation.z), 1); // 1 decimal place — matches the UI's own rounding

  // --- Step 6: Today's Brief reflects the post-escalation state ------------
  // brief.py has three template branches (single-signal / concentrated-
  // sector / spread-across-sectors) and only the latter two ever render an
  // "extreme-severity move" clause — asserting that substring unconditionally
  // is wrong whenever exactly one signal is active (a real, valid outcome:
  // it just means every other flag got acked or never fired this run). All
  // three branches DO always name the single strongest-by-|z| signal
  // explicitly, and our escalated flag — genuinely `extreme` — is the
  // overwhelmingly likely strongest one, so assert on that instead: the
  // brief paragraph (not a digest row's own explanation, which never
  // mentions a ticker name) must name this specific ticker.
  const briefParagraph = page.locator("p").filter({ hasText: escalatedBareTicker });
  await expect(briefParagraph).toBeVisible({ timeout: 10_000 });
});
