"use client";

import { useEffect, useState } from "react";
import { Check, ChevronRight, Layers, Target } from "lucide-react";
import { ACK_DWELL_MS, scheduleDwellAck } from "@/lib/dwell";
import { explainFlag } from "@/lib/explain";
import { directionFromFlag } from "@/lib/severity";
import type { Flag, TickerInfo } from "@/lib/types";
import { DirectionArrow, SeverityBadge } from "./SeverityBadge";

const SEVERITY_STRIPE: Record<Flag["severity"], string> = {
  extreme: "bg-extreme",
  significant: "bg-significant",
  notable: "bg-notable/50",
};

export function DigestRow({
  flag,
  info,
  selected,
  onAck,
  onSelect,
}: {
  flag: Flag;
  /** Real ticker metadata (name/sector) from GET /tickers, looked up by the
   * caller — Flag itself doesn't carry these, so this is undefined until
   * the universe has loaded; the row degrades gracefully without it. */
  info?: TickerInfo;
  selected?: boolean;
  onAck: (flagId: number) => void;
  onSelect: (flag: Flag) => void;
}) {
  // Stage 2 design: ack becomes eligible only after a short dwell on the
  // rendered row, not on mount — prevents an accidental instant-dismiss the
  // moment a fresh digest renders.
  const [ackEligible, setAckEligible] = useState(false);

  useEffect(() => {
    setAckEligible(false);
    const cancel = scheduleDwellAck(ACK_DWELL_MS, () => setAckEligible(true));
    return cancel;
  }, [flag.id]);

  const bareTicker = flag.ticker.replace(/\.NS$/, "");
  const direction = directionFromFlag(flag);
  const dirTextClass = direction === "up" ? "text-up-strong" : "text-down-strong";
  const time = new Date(flag.computed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const zScore = flag.z_score ?? 0;

  return (
    <article
      className={`animate-row-in group relative flex flex-col gap-4 bg-surface-raised px-4 py-5 transition-colors sm:px-6 md:flex-row md:items-start md:gap-6 ${
        selected ? "bg-cobalt/5 ring-1 ring-inset ring-cobalt/40" : "hover:bg-surface-hover"
      }`}
    >
      <span
        aria-hidden="true"
        className={`absolute inset-y-0 left-0 ${selected ? "w-1 bg-cobalt" : `w-[3px] ${SEVERITY_STRIPE[flag.severity]}`}`}
      />

      {/* Unusualness first — this is the point of the product. */}
      <div className="flex items-center gap-4 md:w-40 md:flex-shrink-0 md:flex-col md:items-start md:gap-1.5">
        <div className="flex items-baseline gap-1">
          <span className={`num font-display text-3xl font-bold leading-none ${dirTextClass}`}>
            {Math.abs(zScore).toFixed(1)}σ
          </span>
          <DirectionArrow direction={direction} className={dirTextClass} />
        </div>
        <span className="text-xs text-ink-muted">{direction === "up" ? "above" : "below"} its normal range</span>
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <button onClick={() => onSelect(flag)} className="focus-ring rounded">
            <h3 className="font-display text-base font-semibold tracking-tight text-ink">{bareTicker}</h3>
          </button>
          {/* The seeded universe's `name` field is currently identical to the
              bare ticker for every real ticker (no distinct company names in
              this dataset) — guarded so it never renders a redundant
              duplicate of the ticker text right next to it. */}
          {info?.name && info.name !== bareTicker && <span className="truncate text-sm text-ink-muted">{info.name}</span>}
          <SeverityBadge severity={flag.severity} />
        </div>

        {(flag.volume_ratio != null || flag.sector_relative != null || info?.sector) && (
          <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-ink-muted">
            {flag.volume_ratio != null && (
              <div className="flex items-center gap-1.5">
                <dt className="sr-only">Volume</dt>
                <dd className="num">{flag.volume_ratio.toFixed(1)}× typical volume</dd>
              </div>
            )}
            {flag.sector_relative != null && (
              <div className="flex items-center gap-1.5">
                {flag.sector_relative === "stock_specific" ? (
                  <Target className="size-3.5" aria-hidden="true" />
                ) : (
                  <Layers className="size-3.5" aria-hidden="true" />
                )}
                <dd>{flag.sector_relative === "stock_specific" ? "Stock-specific move" : "Sector-wide move"}</dd>
              </div>
            )}
            {info?.sector && (
              <div className="hidden sm:block">
                <dt className="sr-only">Sector</dt>
                <dd>{info.sector}</dd>
              </div>
            )}
          </dl>
        )}

        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink/85">{explainFlag(flag)}</p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            onClick={() => onSelect(flag)}
            aria-pressed={selected}
            className={`focus-ring inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
              selected
                ? "border-cobalt bg-cobalt text-white hover:bg-cobalt/90"
                : "border-border bg-surface-raised text-ink hover:bg-surface-subtle"
            }`}
          >
            {selected ? "Viewing evidence" : "Show evidence"}
            <ChevronRight className="size-4" aria-hidden="true" />
          </button>
          <button
            onClick={() => onAck(flag.id)}
            disabled={!ackEligible}
            title={ackEligible ? "Acknowledge this signal" : "Reviewing…"}
            className="focus-ring inline-flex items-center gap-1 rounded-md bg-surface-subtle px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-border disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Check className="size-3.5" aria-hidden="true" />
            Acknowledge
          </button>
          <time className="tnum ml-auto text-xs text-ink-muted">Flagged {time}</time>
        </div>
      </div>
    </article>
  );
}
