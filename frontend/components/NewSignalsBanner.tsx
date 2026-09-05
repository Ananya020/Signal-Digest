"use client";

import { Bell } from "lucide-react";

/** Calm, non-disruptive "since you last checked" affordance — the pull-in
 * gate for background poll updates (see lib/digestPoll.ts's `viewed` vs.
 * `latest` split in page.tsx). A background poll revealing new/changed
 * flags never silently rewrites what's on screen; this is the only way
 * they get pulled in. */
export function NewSignalsBanner({ count, onReview }: { count: number; onReview: () => void }) {
  if (count === 0) return null;

  return (
    <div
      className="animate-banner-in flex items-center justify-between gap-4 rounded-lg border border-border bg-cobalt-wash px-4 py-2.5"
      role="status"
      aria-live="polite"
    >
      <p className="flex items-center gap-2 text-sm text-cobalt">
        <Bell className="size-4" aria-hidden="true" />
        <span>
          <span className="num font-semibold">{count}</span> new {count === 1 ? "signal" : "signals"} since you last
          checked
        </span>
      </p>
      <button
        onClick={onReview}
        className="focus-ring shrink-0 rounded-md border border-border bg-surface-raised px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-surface-subtle"
      >
        Review new signals
      </button>
    </div>
  );
}
