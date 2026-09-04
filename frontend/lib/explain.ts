import type { Flag } from "./types";

/** Deterministic, template-based one-line explanation — no LLM call, per
 * PRODUCT.md's locked decision (the deterministic template is the default
 * AND final target for this field, not a placeholder). Built purely from
 * the flag's own stored fields. */
export function explainFlag(flag: Flag): string {
  const bareTicker = flag.ticker.replace(/\.NS$/, "");

  if (flag.signal_type === "volatility_regime") {
    return `${bareTicker}'s short-term volatility has diverged notably from its usual pattern — trading has become choppier than normal.`;
  }

  const z = flag.z_score ?? 0;
  const direction = z >= 0 ? "above" : "below";
  const magnitude = Math.abs(z).toFixed(1);

  const volumeClause =
    flag.volume_ratio != null
      ? `on ${flag.volume_ratio.toFixed(1)}x normal volume`
      : "with no volume data available this cycle";

  const sectorClause =
    flag.sector_relative === "sector_wide"
      ? ", moving with its sector"
      : flag.sector_relative === "stock_specific"
        ? ", while its sector stayed flat"
        : "";

  return `${bareTicker} moved ${magnitude}σ ${direction} its normal range ${volumeClause}${sectorClause}.`;
}
