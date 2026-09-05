"use client";

import { ShieldCheck } from "lucide-react";
import type { Flag, TickerInfo } from "@/lib/types";
import { DigestRow } from "./DigestRow";
import { NewSignalsBanner } from "./NewSignalsBanner";
import { SkeletonRows } from "./SkeletonRows";

export function DigestList({
  flags,
  error,
  selectedFlagId,
  pendingNewCount,
  tickerInfo,
  onPullInNew,
  onAck,
  onSelect,
}: {
  flags: Flag[] | null;
  error: string | null;
  selectedFlagId?: number | null;
  pendingNewCount: number;
  /** Real ticker metadata (name/sector) keyed by ticker, from GET /tickers. */
  tickerInfo?: Record<string, TickerInfo>;
  onPullInNew: () => void;
  onAck: (flagId: number) => void;
  onSelect: (flag: Flag) => void;
}) {
  if (error) {
    return (
      <div className="rounded-md bg-down-wash px-3 py-4 text-sm text-down-text">
        Couldn&apos;t load the digest: {error}
      </div>
    );
  }

  return (
    <section aria-labelledby="digest-heading" className="flex flex-col gap-3">
      <NewSignalsBanner count={pendingNewCount} onReview={onPullInNew} />

      <div className="flex items-baseline justify-between px-1">
        <h2 id="digest-heading" className="eyebrow">
          Signal digest
        </h2>
        <p className="text-xs text-ink-muted">Ordered by how unusual, not by size of move</p>
      </div>

      <div className="divide-y divide-hairline overflow-hidden rounded-xl border border-border shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
        {flags === null ? (
          <SkeletonRows />
        ) : flags.length === 0 ? (
          <div className="flex flex-col items-center gap-3 bg-surface-raised px-6 py-16 text-center">
            <ShieldCheck className="size-8 text-cobalt" aria-hidden="true" />
            <h3 className="font-display text-lg font-semibold text-ink">Nothing unusual right now</h3>
            <p className="max-w-sm text-sm text-ink-muted">
              Your watchlist is behaving within its normal range. We&apos;ll surface a signal the moment a
              stock moves beyond 2σ of its own recent behavior.
            </p>
          </div>
        ) : (
          flags.map((flag) => (
            <DigestRow
              key={flag.id}
              flag={flag}
              info={tickerInfo?.[flag.ticker]}
              selected={flag.id === selectedFlagId}
              onAck={onAck}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
    </section>
  );
}
