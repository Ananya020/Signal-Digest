import { defineConfig, devices } from "@playwright/test";

/** E2E demo-rehearsal config. Deliberately does NOT try to launch Postgres
 * — that's a prerequisite (`docker compose up -d postgres` from the repo
 * root), documented in README.md, same as every manual rehearsal. The
 * backend/frontend dev servers ARE launched here so the whole thing is
 * runnable via one command, but `reuseExistingServer` means it will happily
 * attach to servers you already have running instead of double-starting. */
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000, // the escalation-flip step waits on a real scheduler; see e2e/demo-rehearsal.spec.ts
  fullyParallel: false, // the whole spec is one serial rehearsal against shared backend state
  retries: 0, // a flaky step should be reported, not silently retried into a pass
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "python -m uvicorn app.main:app --port 8000",
      cwd: "../backend",
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
      env: {
        DEMO_MODE: "true",
        SCHEDULER_INTERVAL_SECONDS: "2",
      },
    },
    {
      command: "npm run dev",
      cwd: ".",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
