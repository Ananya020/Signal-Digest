"use client";

import { useState } from "react";
import { ChevronDown, Layers } from "lucide-react";
import type { DigestEvent, Flag, TickerInfo } from "@/lib/types";
import { DigestRow } from "./DigestRow";

/** Step B: a 2+-member sector-wide cluster, collapsed by default. Expanding
 * reveals the existing real DigestRow for each member — ack/select wiring
 * is entirely reused, not reinvented. A single-member sector never reaches
 * this component (DigestList only builds one when an event has 2+ members). */
export function DigestEventCard({
  event,
  members,
  selectedFlagId,
  tickerInfo,
  onAck,
  onSelect,
}: {
  event: DigestEvent;
  members: Flag[];
  selectedFlagId?: number | null;
  tickerInfo?: Record<string, TickerInfo>;
  onAck: (flagId: number) => void;
  onSelect: (flag: Flag) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const bareTickers = event.tickers.map((t) => t.replace(/\.NS$/, ""));

  return (
    <div className="bg-surface-raised">
      <button
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="focus-ring flex w-full items-center gap-4 px-4 py-5 text-left transition-colors hover:bg-surface-hover sm:px-6"
      >
        <div className="flex items-center gap-4 md:w-40 md:flex-shrink-0 md:flex-col md:items-start md:gap-1.5">
          <div className="flex items-baseline gap-1">
            <span className="num font-display text-3xl font-bold leading-none text-ink">
              {event.strongest_z_score.toFixed(1)}σ
            </span>
          </div>
          <span className="text-xs text-ink-muted">strongest in cluster</span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Layers className="size-4 text-ink-muted" aria-hidden="true" />
            <h3 className="font-display text-base font-semibold tracking-tight text-ink">
              {event.sector}: {members.length} stocks moving together
            </h3>
          </div>
          <p className="mt-2 text-sm text-ink-muted">{bareTickers.join(", ")}</p>
        </div>

        <ChevronDown
          className={`size-5 flex-shrink-0 text-ink-muted transition-transform ${expanded ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>

      {expanded && (
        <div className="divide-y divide-hairline border-t border-hairline">
          {members.map((flag) => (
            <DigestRow
              key={flag.id}
              flag={flag}
              info={tickerInfo?.[flag.ticker]}
              selected={flag.id === selectedFlagId}
              onAck={onAck}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}
