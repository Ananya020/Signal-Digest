import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // e2e/ is Playwright's tree (real browser + real backend), not vitest's —
    // exclude it explicitly, otherwise vitest's default *.spec.ts pattern
    // tries to collect it too and fails on the @playwright/test import.
    exclude: ["**/node_modules/**", "**/e2e/**"],
  },
  resolve: {
    alias: {
      "@": import.meta.dirname,
    },
  },
});
