import { FRESHNESS_CONFIG } from "@/lib/severity";
import type { ProviderStatus } from "@/lib/types";
import { Badge } from "./Badge";

export function FreshnessBanner({ status }: { status: ProviderStatus | null }) {
  if (!status) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900">
        Checking data freshness…
      </div>
    );
  }

  const config = FRESHNESS_CONFIG[status.state];
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-md border px-3 py-2 ${config.bgClass} ${config.borderClass}`}
    >
      <div className="flex items-center gap-2">
        <Badge config={config} size="md" />
        <span className="text-sm text-zinc-600">
          {status.age_seconds < 1
            ? "updated just now"
            : `updated ${Math.round(status.age_seconds)}s ago`}
        </span>
      </div>
      <span className="hidden text-xs text-zinc-500 sm:inline">{status.detail}</span>
    </div>
  );
}
