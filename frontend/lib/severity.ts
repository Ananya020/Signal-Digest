import type { Flag, Freshness, Severity } from "./types";

export type Direction = "up" | "down";

/** Direction comes from the sign of the flag's own z_score — never
 * invented. Only meaningful for price_zscore flags (volatility_regime has
 * no z_score and isn't surfaced in the digest); defaults to "up" as a
 * harmless fallback if ever called on one. */
export function directionFromFlag(flag: Pick<Flag, "z_score">): Direction {
  return (flag.z_score ?? 0) >= 0 ? "up" : "down";
}

interface DirectionHue {
  washClass: string; // Notable — lightest wash
  softClass: string; // Significant — medium fill
  strongClass: string; // Extreme — boldest solid fill
  textClass: string; // accent text color at this hue
  arrow: string;
}

// Two independent visual channels, resolved separately and only combined at
// the end: HUE = price direction (this table), INTENSITY = severity (below).
// They must never be conflated into a single color decision.
const DIRECTION_HUE: Record<Direction, DirectionHue> = {
  up: { washClass: "bg-up-wash", softClass: "bg-up-soft", strongClass: "bg-up-strong", textClass: "text-up-text", arrow: "▲" },
  down: { washClass: "bg-down-wash", softClass: "bg-down-soft", strongClass: "bg-down-strong", textClass: "text-down-text", arrow: "▼" },
};

interface SeverityMeta {
  label: string;
  icon: string; // secondary, non-color cue — must still read with hue removed
  barWidthClass: string;
  tickerWeightClass: string;
}

// Icons here are deliberately NOT arrows (▲/▼ are reserved for direction,
// above) so severity's shape cue and direction's arrow cue never collide.
export const SEVERITY_META: Record<Severity, SeverityMeta> = {
  notable: { label: "Notable", icon: "●", barWidthClass: "border-l-2", tickerWeightClass: "font-medium" },
  significant: { label: "Significant", icon: "◆", barWidthClass: "border-l-[3px]", tickerWeightClass: "font-semibold" },
  extreme: { label: "Extreme", icon: "■", barWidthClass: "border-l-4", tickerWeightClass: "font-bold" },
};

export interface ResolvedRowStyle {
  label: string;
  icon: string;
  arrow: string;
  direction: Direction;
  barWidthClass: string;
  barColorClass: string;
  tickerWeightClass: string;
  rowBgClass: string;
  badgeBgClass: string;
  badgeTextClass: string;
  arrowTextClass: string;
}

/** Resolves severity (intensity/weight) and direction (hue) into concrete
 * classes for one digest row. Severity walks the wash→soft→strong ramp
 * WITHIN whichever hue direction supplies; it never changes the hue
 * itself, and direction never changes intensity.
 *
 * Row background caps at "soft" (never the full solid "strong" fill) even
 * for Extreme — a saturated fill across the WHOLE row would make the dark
 * ticker/body text illegible on top of it. "Boldest fill saturation" for
 * Extreme instead concentrates on the small badge chip, which properly
 * inverts to white text at that intensity — a small element can carry full
 * saturation where a full row can't. Extreme still reads as most prominent
 * via the thickest bar, boldest ticker weight, and that solid badge. */
export function resolveRowStyle(severity: Severity, direction: Direction): ResolvedRowStyle {
  const hue = DIRECTION_HUE[direction];
  const meta = SEVERITY_META[severity];
  const rowBgClass = severity === "notable" ? hue.washClass : hue.softClass;
  const badgeBgClass = severity === "notable" ? hue.washClass : severity === "significant" ? hue.softClass : hue.strongClass;
  const barColorClass = direction === "up" ? "border-l-up-strong" : "border-l-down-strong";
  const badgeTextClass = severity === "extreme" ? "text-white" : hue.textClass;

  return {
    label: meta.label,
    icon: meta.icon,
    arrow: hue.arrow,
    direction,
    barWidthClass: meta.barWidthClass,
    barColorClass,
    tickerWeightClass: meta.tickerWeightClass,
    rowBgClass,
    badgeBgClass,
    badgeTextClass,
    arrowTextClass: hue.textClass,
  };
}

const SEVERITY_RANK_LABEL: Record<1 | 2 | 3, string> = { 1: "NOTABLE", 2: "SIGNIFICANT", 3: "EXTREME" };

/** Step A: renders the "since you last checked" delta line, or null when
 * there's nothing to show (no prior ack history, or an unchanged snapshot
 * — the caller/API already filters the latter, but this stays defensive). */
export function formatSinceLastAck(
  current: { z_score: number | null; severity_rank: 1 | 2 | 3 },
  since: { severity_rank_at_ack: 1 | 2 | 3 | null; z_score_at_ack: number | null } | null,
): string | null {
  if (!since) return null;
  const currentZ = Math.abs(current.z_score ?? 0);
  const priorZ = since.z_score_at_ack !== null ? Math.abs(since.z_score_at_ack) : null;
  const zDelta = priorZ !== null ? currentZ - priorZ : null;
  const zPart = zDelta !== null ? `${zDelta >= 0 ? "↑" : "↓"} ${Math.abs(zDelta).toFixed(1)}σ since you last checked` : "Since you last checked";
  const priorLabel = since.severity_rank_at_ack !== null ? SEVERITY_RANK_LABEL[since.severity_rank_at_ack] : null;
  const currentLabel = SEVERITY_RANK_LABEL[current.severity_rank];
  const severityPart = priorLabel && priorLabel !== currentLabel ? ` · was ${priorLabel}, now ${currentLabel}` : "";
  return `${zPart}${severityPart}`;
}

export interface BadgeConfig {
  label: string;
  icon: string;
  textClass: string;
  bgClass: string;
  borderClass: string;
}

// Five genuinely graduated steps — not five labels sharing three colors.
// Strong-green (freshest) → soft-green → soft-amber → strong-amber → red,
// so every state is visually distinguishable at a glance, not just by
// reading its label text.
export const FRESHNESS_CONFIG: Record<Freshness, BadgeConfig> = {
  LIVE: { label: "Live", icon: "●", textClass: "text-fresh-live", bgClass: "bg-fresh-live-wash", borderClass: "border-transparent" },
  RECENT: { label: "Recent", icon: "◐", textClass: "text-fresh-recent", bgClass: "bg-fresh-recent-wash", borderClass: "border-transparent" },
  DELAYED: { label: "Delayed", icon: "◐", textClass: "text-fresh-delayed", bgClass: "bg-fresh-delayed-wash", borderClass: "border-transparent" },
  STALE: { label: "Stale", icon: "●", textClass: "text-fresh-stale", bgClass: "bg-fresh-stale-wash", borderClass: "border-transparent" },
  UNAVAILABLE: { label: "Unavailable", icon: "✕", textClass: "text-fresh-unavailable", bgClass: "bg-fresh-unavailable-wash", borderClass: "border-transparent" },
};
