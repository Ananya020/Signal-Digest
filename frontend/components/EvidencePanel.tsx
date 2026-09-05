"use client";

import { useEffect, useState } from "react";
import { Check, Layers, Target } from "lucide-react";
import { fetchTickerFlags } from "@/lib/api";
import { buildHistogram, nearestBinCenter } from "@/lib/histogram";
import { ACK_DWELL_MS, scheduleDwellAck } from "@/lib/dwell";
import { directionFromFlag, SEVERITY_META, type Direction } from "@/lib/severity";
import type { EvidenceResponse, Flag, HistoricalFlag } from "@/lib/types";
import { DirectionArrow, SeverityBadge } from "./SeverityBadge";

const SEVERITY_BAND_TEXT: Record<Flag["severity"], string> = {
  notable: "|z| in [2.0, 2.5)",
  significant: "|z| in [2.5, 3.5)",
  extreme: "|z| ≥ 3.5",
};

const CHART_WIDTH = 520;
const CHART_HEIGHT = 160;
const PADDING_X = 8;
const PADDING_TOP = 22;
const PADDING_BOTTOM = 4;

/** Hand-rolled inline SVG bar chart — this project's evidence chart is
 * deliberately not built on a charting library (see ARCHITECTURE.md).
 * ui_reference.md's DistributionChart uses recharts over a pre-bucketed
 * `signal.distribution` array; the real /evidence endpoint returns raw
 * daily-return points instead (see lib/histogram.ts's client-side bucketing
 * step), so this ports the reference's visual structure — a return
 * histogram with the ±2σ normal range highlighted and today's point marked
 * by a reference line — onto real data and this project's existing
 * hand-rolled-SVG approach, rather than adding a charting dependency. */
function DistributionChart({
  evidence,
  direction,
}: {
  evidence: EvidenceResponse;
  direction: Direction;
}) {
  const returns = evidence.points.map((p) => p.return);
  const bins = buildHistogram(returns, 12);
  const maxCount = Math.max(1, ...bins.map((b) => b.count));
  const band = evidence.stdev_return ?? 0;
  const lower = evidence.mean_return - 2 * band;
  const upper = evidence.mean_return + 2 * band;
  const todayCenter = nearestBinCenter(bins, evidence.flagged_point.return);

  const plotWidth = CHART_WIDTH - 2 * PADDING_X;
  const plotHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const barGap = 2;
  const barWidth = bins.length > 0 ? plotWidth / bins.length - barGap : 0;
  const dirStrongClass = direction === "up" ? "fill-up-strong" : "fill-down-strong";
  const dirTextClass = direction === "up" ? "text-up-strong" : "text-down-strong";

  return (
    <figure className="mt-3">
      <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="h-40 w-full" role="img" aria-label={`Distribution of daily returns for ${evidence.ticker}, last ${evidence.points.length} sessions, with today's move marked`}>
        {bins.map((bin, i) => {
          const height = (bin.count / maxCount) * plotHeight;
          const x = PADDING_X + i * (barWidth + barGap);
          const y = PADDING_TOP + plotHeight - height;
          const inRange = bin.center >= lower && bin.center <= upper;
          return (
            <rect
              key={i}
              x={x}
              y={y}
              width={barWidth}
              height={height}
              rx={2}
              className={inRange ? "fill-cobalt" : "fill-border-strong"}
            />
          );
        })}
        {bins.length > 0 && (
          <>
            <line
              x1={PADDING_X + ((todayCenter - bins[0].center) / (bins.at(-1)!.center - bins[0].center || 1)) * plotWidth}
              x2={PADDING_X + ((todayCenter - bins[0].center) / (bins.at(-1)!.center - bins[0].center || 1)) * plotWidth}
              y1={PADDING_TOP}
              y2={CHART_HEIGHT - PADDING_BOTTOM}
              strokeWidth={2}
              className={direction === "up" ? "stroke-up-strong" : "stroke-down-strong"}
            />
            <text
              x={PADDING_X + ((todayCenter - bins[0].center) / (bins.at(-1)!.center - bins[0].center || 1)) * plotWidth}
              y={PADDING_TOP - 8}
              textAnchor="middle"
              fontSize="10"
              className={dirTextClass}
            >
              Today
            </text>
          </>
        )}
      </svg>
      <figcaption className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-muted">
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-sm bg-cobalt" aria-hidden="true" /> Normal range (±2σ)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-sm bg-border-strong" aria-hidden="true" /> Tail observations
        </span>
        <span className="flex items-center gap-1.5">
          <span className={`h-3 w-0.5 ${dirStrongClass.replace("fill-", "bg-")}`} aria-hidden="true" />
          Today&apos;s observation
        </span>
        <span>Distribution of daily returns, last {evidence.points.length} sessions</span>
      </figcaption>
    </figure>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="py-3">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="num mt-0.5 font-display text-base font-semibold tracking-tight text-ink">{value}</dd>
      {hint && <p className="mt-0.5 text-[11px] text-ink-muted">{hint}</p>}
    </div>
  );
}

/** A condensed inline version of HistoryPanel's real-data row rendering
 * (fetch + render only, no dialog chrome) — the drawer embeds "earlier
 * signals" directly rather than launching a second modal on top of itself. */
function EarlierSignals({ ticker }: { ticker: string }) {
  const [flags, setFlags] = useState<HistoricalFlag[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    setFlags(null);
    fetchTickerFlags(ticker)
      .then((data) => {
        if (!cancelled) setFlags(data.slice(0, 5));
      })
      .catch(() => {
        if (!cancelled) setFlags([]);
      });
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  if (flags === null) return <p className="mt-2 text-sm text-ink-muted">Loading…</p>;
  if (flags.length === 0) return <p className="mt-2 text-sm text-ink-muted">No earlier signals recorded.</p>;

  return (
    <ul className="mt-2 divide-y divide-hairline">
      {flags.map((flag, i) => (
        <li key={`${flag.trading_day}-${flag.signal_type}-${i}`} className="flex items-center justify-between gap-3 py-2">
          <span className="text-xs text-ink-muted">{flag.trading_day}</span>
          <span className="text-xs font-medium text-ink">{SEVERITY_META[flag.severity].label}</span>
        </li>
      ))}
    </ul>
  );
}

export function EvidencePanel({
  flag,
  evidence,
  loading,
  error,
  onAck,
  onClose,
}: {
  flag: Flag;
  evidence: EvidenceResponse | null;
  loading: boolean;
  error: string | null;
  onAck: (flagId: number) => void;
  onClose: () => void;
}) {
  const direction = directionFromFlag(flag);
  const bareTicker = flag.ticker.replace(/\.NS$/, "");
  const [ackEligible, setAckEligible] = useState(false);

  useEffect(() => {
    setAckEligible(false);
    const cancel = scheduleDwellAck(ACK_DWELL_MS, () => setAckEligible(true));
    return cancel;
  }, [flag.id]);

  return (
    <div className="fixed inset-0 z-10 flex items-stretch justify-end bg-ink/30" onClick={onClose}>
      <div
        className="animate-panel-in flex w-full max-w-lg flex-col overflow-y-auto border-l border-border-strong bg-surface-raised shadow-[0_12px_32px_-4px_rgba(15,23,42,0.06),0_4px_8px_-2px_rgba(15,23,42,0.03)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-hairline px-5 pb-4 pt-5">
          <div className="mb-1 flex items-center justify-between">
            <p className="eyebrow">Show your work</p>
            <button onClick={onClose} className="focus-ring rounded text-ink-muted hover:text-ink" aria-label="Close">
              ✕
            </button>
          </div>
          <h2 className="flex flex-wrap items-center gap-3 font-display text-xl text-ink">
            {bareTicker}
            <SeverityBadge severity={flag.severity} />
          </h2>
        </div>

        <div className="flex-1 px-5 py-5">
          {loading && <p className="py-8 text-center text-sm text-ink-muted">Loading evidence…</p>}
          {error && <p className="py-8 text-center text-sm text-down-text">Couldn&apos;t load evidence: {error}</p>}

          {evidence && !loading && !error && (
            <>
              <p className="text-[15px] leading-relaxed text-ink">
                Today&apos;s{" "}
                <span className="inline-flex items-center gap-0.5 align-middle">
                  <DirectionArrow
                    direction={direction}
                    className={direction === "up" ? "text-up-strong" : "text-down-strong"}
                  />
                  <span className="num font-semibold">{(evidence.flagged_point.return * 100).toFixed(2)}%</span>
                </span>{" "}
                move is{" "}
                <span className="num font-semibold">{Math.abs(evidence.flagged_point.z_score ?? 0).toFixed(2)}σ</span>{" "}
                {direction === "up" ? "above" : "below"} {bareTicker}&apos;s recent average daily return.
                {flag.volume_ratio != null && (
                  <>
                    {" "}
                    Volume is <span className="num font-semibold">{flag.volume_ratio.toFixed(1)}×</span> its typical
                    level.
                  </>
                )}
              </p>

              <DistributionChart evidence={evidence} direction={direction} />

              <hr className="my-5 border-hairline" />

              <h3 className="eyebrow">The calculation</h3>
              <div className="mt-2 rounded-lg border border-border bg-surface-subtle px-4 py-3">
                <p className="num text-[13px] leading-relaxed text-ink/85">
                  z = (today − mean) / σ = ({(evidence.flagged_point.return * 100).toFixed(2)}% −{" "}
                  {(evidence.mean_return * 100).toFixed(2)}%) /{" "}
                  {evidence.stdev_return != null ? (evidence.stdev_return * 100).toFixed(2) : "n/a"}% ={" "}
                  <span className="font-semibold">{evidence.flagged_point.z_score?.toFixed(2) ?? "n/a"}</span>
                </p>
                <p className="mt-1.5 text-[11px] text-ink-muted">
                  Deterministic, same input → same output. Threshold |z| ≥ 2.0. This severity band ={" "}
                  {SEVERITY_BAND_TEXT[flag.severity]}.
                </p>
              </div>

              <dl className="mt-2 grid grid-cols-2 gap-x-6 divide-y divide-hairline sm:grid-cols-3">
                <Stat label="Today's return" value={`${(evidence.flagged_point.return * 100).toFixed(2)}%`} />
                <Stat label="Z-score" value={evidence.flagged_point.z_score?.toFixed(2) ?? "n/a"} />
                <Stat
                  label="Historical mean"
                  value={`${(evidence.mean_return * 100).toFixed(2)}%`}
                  hint={`${evidence.window_start} to ${evidence.window_end}`}
                />
                <Stat
                  label="Std deviation"
                  value={evidence.stdev_return != null ? `${(evidence.stdev_return * 100).toFixed(2)}%` : "n/a"}
                />
                {flag.volume_ratio != null && (
                  <Stat label="Volume ratio" value={`${flag.volume_ratio.toFixed(1)}×`} hint="annotation only" />
                )}
              </dl>

              {flag.sector_relative != null && (
                <>
                  <hr className="my-5 border-hairline" />
                  <h3 className="eyebrow flex items-center gap-1.5">
                    {flag.sector_relative === "stock_specific" ? (
                      <Target className="size-3.5" aria-hidden="true" />
                    ) : (
                      <Layers className="size-3.5" aria-hidden="true" />
                    )}
                    Sector-relative context
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink/85">
                    {flag.sector_relative === "stock_specific"
                      ? "This move is not explained by how the broader sector moved today, so it's treated as stock-specific."
                      : "Peers in the same sector moved together today, so this is treated as a sector-wide move."}
                  </p>
                </>
              )}

              <hr className="my-5 border-hairline" />

              <h3 className="eyebrow">Earlier signals for {bareTicker}</h3>
              <EarlierSignals ticker={flag.ticker} />

              <p className="mt-6 text-[11px] leading-relaxed text-ink-muted">
                Demo data is a replay of real historical market data. Signal Digest is research tooling, not
                investment advice.
              </p>
            </>
          )}
        </div>

        <div className="sticky bottom-0 flex gap-2 border-t border-hairline bg-surface-raised px-5 py-3">
          <button
            onClick={() => {
              onAck(flag.id);
              onClose();
            }}
            disabled={!ackEligible}
            className="focus-ring inline-flex flex-1 items-center justify-center gap-1 rounded-md bg-surface-subtle px-3 py-2 text-sm font-medium text-ink transition-colors hover:bg-border disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Check className="size-4" aria-hidden="true" />
            Acknowledge signal
          </button>
          <button
            onClick={onClose}
            className="focus-ring rounded-md px-3 py-2 text-sm font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
