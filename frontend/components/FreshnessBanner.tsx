import type { Freshness, ProviderStatus } from "@/lib/types";

/** Calm, user-facing language only — no internal/debug values (replay
 * step, raw mode string, frozen timestamps). Those live in the demo
 * controls panel, where they're useful for live narration. This is a
 * system-health signal, a separate channel from the digest's price
 * direction/severity system — it never borrows that hue vocabulary. */
const CONFIG: Record<Freshness, { label: string; dotClass: string; pulse: boolean }> = {
  LIVE: { label: "Live", dotClass: "bg-fresh-live", pulse: true },
  RECENT: { label: "Recent", dotClass: "bg-fresh-recent", pulse: false },
  DELAYED: { label: "Delayed", dotClass: "bg-fresh-delayed", pulse: false },
  STALE: { label: "Stale", dotClass: "bg-fresh-stale", pulse: false },
  UNAVAILABLE: { label: "Unavailable", dotClass: "bg-fresh-unavailable", pulse: false },
};

function detail(state: Freshness, ageSeconds: number): string {
  const seconds = Math.round(ageSeconds);
  const minutes = Math.round(ageSeconds / 60);
  switch (state) {
    case "LIVE":
    case "RECENT":
      return `Updated ${seconds}s ago`;
    case "DELAYED":
      return `Running a little behind — last updated ${seconds}s ago`;
    case "STALE":
      return `Data hasn't refreshed in ${minutes} min. New signals are paused.`;
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

  const config = CONFIG[status.state];

  return (
    <div
      className="flex items-center gap-3 rounded-md bg-surface-subtle px-3 py-2 transition-colors duration-300"
      role="status"
      aria-live="polite"
    >
      <span className="relative flex size-2 shrink-0 items-center justify-center">
        <span className={`size-2 rounded-full ${config.dotClass}`} />
        {config.pulse && (
          <span className={`absolute size-2 animate-ping rounded-full opacity-60 ${config.dotClass}`} />
        )}
      </span>
      <span className="leading-tight">
        <span className="eyebrow block">{config.label}</span>
        <span className="num block text-[11px] text-ink-muted">{detail(status.state, status.age_seconds)}</span>
      </span>
    </div>
  );
}
