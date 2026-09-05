"use client";

import { ShieldCheck } from "lucide-react";
import type { DigestEvent, Flag, TickerInfo } from "@/lib/types";
import { DigestEventCard } from "./DigestEventCard";
import { DigestRow } from "./DigestRow";
import { NewSignalsBanner } from "./NewSignalsBanner";
import { SkeletonRows } from "./SkeletonRows";

/** Step B: renders `flags` in their existing rank order, substituting an
 * expandable DigestEventCard at the position of an event's first (i.e.
 * highest-ranked, since `flags` is already |z|-sorted) member, and skipping
 * that event's remaining members as standalone rows — they're reachable
 * inside the card instead. A flag not covered by any event renders exactly
 * as it always has. Pure presentation grouping; ack/select are untouched. */
function buildDigestItems(flags: Flag[], events: DigestEvent[]) {
  const flagsByTicker = new Map<string, Flag>();
  for (const flag of flags) flagsByTicker.set(flag.ticker, flag);

  const eventByTicker = new Map<string, DigestEvent>();
  for (const event of events) {
    for (const ticker of event.tickers) eventByTicker.set(ticker, event);
  }

  const renderedEventSectors = new Set<string>();
  const items: Array<{ type: "flag"; flag: Flag } | { type: "event"; event: DigestEvent; members: Flag[] }> = [];

  for (const flag of flags) {
    const event = eventByTicker.get(flag.ticker);
    if (!event) {
      items.push({ type: "flag", flag });
      continue;
    }
    if (renderedEventSectors.has(event.sector)) continue; // already emitted, member row lives inside the card
    renderedEventSectors.add(event.sector);
    const members = event.tickers.map((t) => flagsByTicker.get(t)).filter((f): f is Flag => f != null);
    items.push({ type: "event", event, members });
  }

  return items;
}

export function DigestList({
  flags,
  events,
  error,
  selectedFlagId,
  pendingNewCount,
  tickerInfo,
  onPullInNew,
  onAck,
  onSelect,
}: {
  flags: Flag[] | null;
  events?: DigestEvent[];
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
          buildDigestItems(flags, events ?? []).map((item) =>
            item.type === "event" ? (
              <DigestEventCard
                key={`event-${item.event.sector}`}
                event={item.event}
                members={item.members}
                selectedFlagId={selectedFlagId}
                tickerInfo={tickerInfo}
                onAck={onAck}
                onSelect={onSelect}
              />
            ) : (
              <DigestRow
                key={item.flag.id}
                flag={item.flag}
                info={tickerInfo?.[item.flag.ticker]}
                selected={item.flag.id === selectedFlagId}
                onAck={onAck}
                onSelect={onSelect}
              />
            ),
          )
        )}
      </div>
    </section>
  );
}
