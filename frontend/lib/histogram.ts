export interface HistogramBin {
  center: number;
  count: number;
}

/** Buckets raw daily returns into evenly-spaced bins for the distribution
 * chart. The real /evidence endpoint returns raw points (not a
 * pre-bucketed histogram, per ui_reference.md's mocked `signal.distribution`
 * shape) — this is the client-side bucketing step that reconciles the two,
 * per the Step 8 data-shape decision (see PROGRESS.md): bucketing a small
 * (~30-60 point) array client-side is simple and cheap, not "genuinely
 * awkward", so no backend change was proposed. */
export function buildHistogram(returns: number[], binCount = 12): HistogramBin[] {
  if (returns.length === 0) return [];

  const min = Math.min(...returns);
  const max = Math.max(...returns);
  const span = max - min || Math.abs(min) || 1;
  const binWidth = span / binCount;

  const bins: HistogramBin[] = Array.from({ length: binCount }, (_, i) => ({
    center: min + binWidth * (i + 0.5),
    count: 0,
  }));

  for (const value of returns) {
    const index = Math.min(binCount - 1, Math.max(0, Math.floor((value - min) / binWidth)));
    bins[index].count += 1;
  }

  return bins;
}

/** The bin whose center is nearest `value` — used to place the "Today"
 * reference marker on the bin it actually falls in. */
export function nearestBinCenter(bins: HistogramBin[], value: number): number {
  return bins.reduce((best, b) => (Math.abs(b.center - value) < Math.abs(best - value) ? b.center : best), bins[0]?.center ?? value);
}
