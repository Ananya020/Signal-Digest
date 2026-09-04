import { FRESHNESS_CONFIG } from "@/lib/severity";
import type { Freshness, ProviderStatus } from "@/lib/types";
import { Badge } from "./Badge";

/** Calm, user-facing language only — no internal/debug values (replay
 * step, raw mode string, frozen timestamps). Those live in the demo
 * controls panel, where they're useful for live narration. This is a
 * system-health signal, a separate channel from the digest's price
 * direction/severity system — it never borrows that hue vocabulary. */
function summarize(state: Freshness, ageSeconds: number): string {
  const minutes = Math.round(ageSeconds / 60);
  switch (state) {
    case "LIVE":
      return "Data is live.";
    case "RECENT":
      return `Updated ${Math.round(ageSeconds)}s ago.`;
    case "DELAYED":
      return `Running a little behind — last updated ${Math.round(ageSeconds)}s ago.`;
    case "STALE":
      return `Market data is stale — last updated ${minutes} min ago. New signals are paused.`;
    case "UNAVAILABLE":
      return "Data feed is unavailable. Showing the last known signals.";
  }
}

export function FreshnessBanner({ status }: { status: ProviderStatus | null }) {
  if (!status) {
    return (
      <div className="flex items-center gap-2 rounded-md bg-surface-subtle px-3 py-2 text-sm text-ink-muted">
        Checking data freshness…
      </div>
    );
  }

  const config = FRESHNESS_CONFIG[status.state];
  return (
    <div className="flex items-center gap-3 rounded-md bg-surface-subtle px-3 py-2 transition-colors duration-300">
      <Badge config={config} size="md" />
      <span className="text-sm text-ink-muted">{summarize(status.state, status.age_seconds)}</span>
    </div>
  );
}
