"use client";

import { Activity, Search } from "lucide-react";
import type { ProviderStatus } from "@/lib/types";
import { DemoControls } from "./DemoControls";
import { FreshnessBanner } from "./FreshnessBanner";

/** Product identity — a deliberate wordmark treatment, not a plain page
 * heading (Workstream 4, PRODUCT.md — kept exactly as delivered there).
 * Restyled to ui_reference.md's AppHeader structure around it: a sticky,
 * bordered bar with an icon badge, a right-aligned control cluster (Add
 * stock, About, Demo controls, freshness).
 *
 * ui_reference.md's watchlist switcher is not ported: this build has no
 * multi-watchlist workstream (bootstrap always attaches to the single
 * existing watchlist, see lib/bootstrap.ts) — a switcher over one item
 * would be inert UI, so it's omitted rather than shipped non-functional.
 * "Add stock" is real, though: it doesn't open a second search UI, it just
 * scrolls to and focuses WatchlistManager's own real search box (see
 * app/page.tsx's `onAddStockClick`) — one real entry point, two ways in. */
export function AppHeader({
  onAboutClick,
  onAddStockClick,
  providerStatus,
  onFaultChanged,
}: {
  onAboutClick: () => void;
  onAddStockClick: () => void;
  providerStatus: ProviderStatus | null;
  onFaultChanged: () => void;
}) {
  return (
    <header className="sticky top-0 z-30 -mx-4 border-b border-hairline bg-canvas/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <span
            className="flex size-7 shrink-0 items-center justify-center rounded-md bg-cobalt text-white"
            aria-hidden="true"
          >
            <Activity className="size-4" />
          </span>
          <div className="min-w-0">
            <div className="font-display flex items-baseline gap-0.5 text-[18px] font-semibold leading-[24px] tracking-[-0.015em]">
              <span className="text-ink-muted">signal</span>
              <span className="text-ink">Digest</span>
            </div>
            <p className="hidden truncate text-[11px] text-ink-muted lg:block">
              Know in five seconds what actually changed — not what always jitters — and why.
            </p>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={onAddStockClick}
            aria-label="Search or add a stock"
            className="focus-ring inline-flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
          >
            <Search className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Add stock</span>
          </button>

          <button
            onClick={onAboutClick}
            className="focus-ring shrink-0 rounded-md px-2.5 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
          >
            About
          </button>

          {providerStatus?.demo_mode && <DemoControls status={providerStatus} onChanged={onFaultChanged} />}

          <div className="hidden border-l border-hairline pl-3 sm:block">
            <FreshnessBanner status={providerStatus} />
          </div>
        </div>

        <div className="w-full sm:hidden">
          <FreshnessBanner status={providerStatus} />
        </div>
      </div>
    </header>
  );
}
