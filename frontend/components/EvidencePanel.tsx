"use client";

import type { EvidenceResponse } from "@/lib/types";

const CHART_WIDTH = 600;
const CHART_HEIGHT = 200;
const PADDING = 24;

function scaleY(value: number, min: number, max: number): number {
  const span = max - min || 1;
  return CHART_HEIGHT - PADDING - ((value - min) / span) * (CHART_HEIGHT - 2 * PADDING);
}

/** Hand-rolled inline SVG — no charting library. Plots the mean±stdev band
 * (the exact band the flag's z_score was computed against, per the Phase 3
 * evidence correction) as a shaded region under the real historical
 * returns, with the flagged day's own point marked distinctly. The
 * flagged point's date may fall outside the plotted window's date range
 * (the baseline is static, see PROGRESS.md) — drawn with a visual gap and
 * its own label so that's never implied to be contiguous when it isn't. */
export function EvidenceChart({ evidence }: { evidence: EvidenceResponse }) {
  const { points, mean_return, stdev_return, flagged_point } = evidence;
  const band = stdev_return ?? 0;

  const allReturns = [...points.map((p) => p.return), flagged_point.return, mean_return + band, mean_return - band];
  const min = Math.min(...allReturns);
  const max = Math.max(...allReturns);

  const plotWidth = CHART_WIDTH - 2 * PADDING - 60; // reserve 60px gap before the flagged point
  const stepX = points.length > 1 ? plotWidth / (points.length - 1) : 0;

  const bandTop = scaleY(mean_return + band, min, max);
  const bandBottom = scaleY(mean_return - band, min, max);
  const meanY = scaleY(mean_return, min, max);
  const flaggedX = PADDING + plotWidth + 40;
  const flaggedY = scaleY(flagged_point.return, min, max);

  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      role="img"
      aria-label={`Return distribution for ${evidence.ticker}: mean ${(mean_return * 100).toFixed(2)}%, stdev ${stdev_return != null ? (stdev_return * 100).toFixed(2) + "%" : "unavailable"}, flagged day return ${(flagged_point.return * 100).toFixed(2)}% (z=${flagged_point.z_score?.toFixed(2) ?? "n/a"})`}
      className="w-full"
    >
      {/* mean +/- 1 stdev band */}
      <rect
        x={PADDING}
        y={Math.min(bandTop, bandBottom)}
        width={plotWidth}
        height={Math.abs(bandBottom - bandTop)}
        fill="currentColor"
        className="text-blue-100 dark:text-blue-950"
      />
      {/* mean line */}
      <line x1={PADDING} x2={PADDING + plotWidth} y1={meanY} y2={meanY} stroke="currentColor" strokeDasharray="4 3" className="text-blue-400" />

      {/* historical points */}
      {points.map((p, i) => (
        <circle
          key={p.date}
          cx={PADDING + i * stepX}
          cy={scaleY(p.return, min, max)}
          r={2.5}
          fill="currentColor"
          className="text-zinc-400"
        />
      ))}

      {/* visual gap marker separating the plotted window from the flagged day */}
      <line
        x1={PADDING + plotWidth + 18}
        x2={PADDING + plotWidth + 18}
        y1={PADDING}
        y2={CHART_HEIGHT - PADDING}
        stroke="currentColor"
        strokeDasharray="2 3"
        className="text-zinc-300"
      />

      {/* the flagged point — outside the band is the whole point */}
      <circle cx={flaggedX} cy={flaggedY} r={5} fill="currentColor" className="text-red-600" />
      <text x={flaggedX} y={flaggedY - 10} textAnchor="middle" fontSize="10" className="fill-red-700">
        {evidence.flagged_point.date}
      </text>
      <text x={flaggedX} y={CHART_HEIGHT - 4} textAnchor="middle" fontSize="9" className="fill-zinc-500">
        flagged day
      </text>
    </svg>
  );
}

export function EvidencePanel({
  evidence,
  loading,
  error,
  onClose,
}: {
  evidence: EvidenceResponse | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div
        className="w-full max-w-xl rounded-lg bg-white p-4 shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Show your work</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600" aria-label="Close">
            ✕
          </button>
        </div>

        {loading && <p className="py-8 text-center text-sm text-zinc-500">Loading evidence…</p>}
        {error && <p className="py-8 text-center text-sm text-red-600">Couldn&apos;t load evidence: {error}</p>}
        {evidence && !loading && !error && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {evidence.ticker.replace(/\.NS$/, "")} — window {evidence.window_start} to {evidence.window_end}
            </p>
            <EvidenceChart evidence={evidence} />
            <div className="grid grid-cols-3 gap-2 text-xs text-zinc-500">
              <span>Mean: {(evidence.mean_return * 100).toFixed(2)}%</span>
              <span>Stdev: {evidence.stdev_return != null ? (evidence.stdev_return * 100).toFixed(2) + "%" : "n/a"}</span>
              <span>Flagged z: {evidence.flagged_point.z_score?.toFixed(2) ?? "n/a"}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
