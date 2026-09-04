"use client";

import { resolveRowStyle, type Direction } from "@/lib/severity";
import type { EvidenceResponse, Severity } from "@/lib/types";

const CHART_WIDTH = 600;
const CHART_HEIGHT = 200;
const PADDING = 28;

function scaleY(value: number, min: number, max: number): number {
  const span = max - min || 1;
  return CHART_HEIGHT - PADDING - ((value - min) / span) * (CHART_HEIGHT - 2 * PADDING);
}

/** Hand-rolled inline SVG — no charting library, no chart chrome, per
 * design.md's restrained aesthetic. Plots the mean±stdev band (the exact
 * band the flag's z_score was computed against) as a shaded region under
 * the real historical returns, with the flagged day's own point marked in
 * its actual severity/direction color. The flagged point's date may fall
 * outside the plotted window's date range (the baseline is static) —
 * drawn with a visual gap and its own label so that's never implied to be
 * contiguous when it isn't. */
export function EvidenceChart({
  evidence,
  severity,
  direction,
}: {
  evidence: EvidenceResponse;
  severity: Severity;
  direction: Direction;
}) {
  const { points, mean_return, stdev_return, flagged_point } = evidence;
  const band = stdev_return ?? 0;
  const style = resolveRowStyle(severity, direction);
  const markColorClass = direction === "up" ? "fill-up-strong" : "fill-down-strong";
  const markTextClass = direction === "up" ? "fill-up-text" : "fill-down-text";

  const allReturns = [...points.map((p) => p.return), flagged_point.return, mean_return + band, mean_return - band];
  const min = Math.min(...allReturns);
  const max = Math.max(...allReturns);

  const plotWidth = CHART_WIDTH - 2 * PADDING - 64; // reserve space before the flagged point
  const stepX = points.length > 1 ? plotWidth / (points.length - 1) : 0;

  const bandTop = scaleY(mean_return + band, min, max);
  const bandBottom = scaleY(mean_return - band, min, max);
  const meanY = scaleY(mean_return, min, max);
  const flaggedX = PADDING + plotWidth + 44;
  const flaggedY = scaleY(flagged_point.return, min, max);

  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      role="img"
      aria-label={`Return distribution for ${evidence.ticker}: mean ${(mean_return * 100).toFixed(2)}%, stdev ${stdev_return != null ? (stdev_return * 100).toFixed(2) + "%" : "unavailable"}, flagged day return ${(flagged_point.return * 100).toFixed(2)}% (z=${flagged_point.z_score?.toFixed(2) ?? "n/a"}), severity ${style.label}`}
      className="w-full"
    >
      {/* normal range: mean +/- 1 stdev */}
      <rect
        x={PADDING}
        y={Math.min(bandTop, bandBottom)}
        width={plotWidth}
        height={Math.abs(bandBottom - bandTop)}
        className="fill-cobalt-wash"
      />
      <line x1={PADDING} x2={PADDING + plotWidth} y1={meanY} y2={meanY} strokeDasharray="4 3" className="stroke-cobalt/50" />
      <text x={PADDING} y={Math.min(bandTop, bandBottom) - 6} fontSize="10" className="fill-ink-muted">
        normal range
      </text>

      {/* real historical points */}
      {points.map((p, i) => (
        <circle key={p.date} cx={PADDING + i * stepX} cy={scaleY(p.return, min, max)} r={2.5} className="fill-ink-muted/60" />
      ))}

      {/* visual gap separating the plotted window from the flagged day */}
      <line
        x1={PADDING + plotWidth + 20}
        x2={PADDING + plotWidth + 20}
        y1={PADDING}
        y2={CHART_HEIGHT - PADDING}
        strokeDasharray="2 4"
        className="stroke-hairline"
      />

      {/* the flagged point — direction sets hue, severity's own label carries
          the intensity meaning (shown in the stats row below) */}
      <circle cx={flaggedX} cy={flaggedY} r={5} className={markColorClass} />
      <text x={flaggedX} y={flaggedY - 10} textAnchor="middle" fontSize="10" className={markTextClass}>
        {evidence.flagged_point.date}
      </text>
      <text x={flaggedX} y={CHART_HEIGHT - 6} textAnchor="middle" fontSize="9" className="fill-ink-muted">
        flagged day
      </text>
    </svg>
  );
}

export function EvidencePanel({
  evidence,
  severity,
  direction,
  loading,
  error,
  onClose,
}: {
  evidence: EvidenceResponse | null;
  severity: Severity;
  direction: Direction;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-ink/30 p-4" onClick={onClose}>
      {/* stopPropagation: a click anywhere inside the panel — including
          where a digest row's Acknowledge button visually sits behind it —
          never reaches anything underneath. Only the backdrop closes it. */}
      <div
        className="animate-panel-in w-full max-w-xl rounded-lg border border-border-strong bg-surface-raised p-4 shadow-[0_12px_32px_-4px_rgba(15,23,42,0.06),0_4px_8px_-2px_rgba(15,23,42,0.03)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">Show your work</h2>
          <button onClick={onClose} className="text-ink-muted hover:text-ink" aria-label="Close">
            ✕
          </button>
        </div>

        {loading && <p className="py-8 text-center text-sm text-ink-muted">Loading evidence…</p>}
        {error && <p className="py-8 text-center text-sm text-down-text">Couldn&apos;t load evidence: {error}</p>}
        {evidence && !loading && !error && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-ink-muted">
              {evidence.ticker.replace(/\.NS$/, "")} — window {evidence.window_start} to {evidence.window_end}
            </p>
            <EvidenceChart evidence={evidence} severity={severity} direction={direction} />
            <div className="tnum grid grid-cols-3 gap-2 border-t border-hairline pt-3 text-xs text-ink-muted">
              <span>Mean {(evidence.mean_return * 100).toFixed(2)}%</span>
              <span>Stdev {evidence.stdev_return != null ? (evidence.stdev_return * 100).toFixed(2) + "%" : "n/a"}</span>
              <span>Flagged z {evidence.flagged_point.z_score?.toFixed(2) ?? "n/a"}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
