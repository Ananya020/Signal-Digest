import type { Freshness, Severity } from "./types";

export interface BadgeConfig {
  label: string;
  icon: string;
  textClass: string;
  bgClass: string;
  borderClass: string;
}

// Accessibility requirement (Stage 5): color is never the only signal —
// every badge always carries a distinct icon glyph AND a text label
// alongside its color. Enforced by SeverityBadge/FreshnessBanner always
// rendering all three fields from this config, never color classes alone.
export const SEVERITY_CONFIG: Record<Severity, BadgeConfig> = {
  notable: {
    label: "Notable",
    icon: "●",
    textClass: "text-amber-800",
    bgClass: "bg-amber-50",
    borderClass: "border-amber-300",
  },
  significant: {
    label: "Significant",
    icon: "▲",
    textClass: "text-orange-800",
    bgClass: "bg-orange-50",
    borderClass: "border-orange-300",
  },
  extreme: {
    label: "Extreme",
    icon: "■",
    textClass: "text-red-800",
    bgClass: "bg-red-50",
    borderClass: "border-red-300",
  },
};

export const FRESHNESS_CONFIG: Record<Freshness, BadgeConfig> = {
  LIVE: {
    label: "Live",
    icon: "●",
    textClass: "text-green-800",
    bgClass: "bg-green-50",
    borderClass: "border-green-300",
  },
  RECENT: {
    label: "Recent",
    icon: "◉",
    textClass: "text-lime-800",
    bgClass: "bg-lime-50",
    borderClass: "border-lime-300",
  },
  DELAYED: {
    label: "Delayed",
    icon: "◐",
    textClass: "text-amber-800",
    bgClass: "bg-amber-50",
    borderClass: "border-amber-300",
  },
  STALE: {
    label: "Stale",
    icon: "◑",
    textClass: "text-orange-800",
    bgClass: "bg-orange-50",
    borderClass: "border-orange-300",
  },
  UNAVAILABLE: {
    label: "Unavailable",
    icon: "✕",
    textClass: "text-red-800",
    bgClass: "bg-red-50",
    borderClass: "border-red-300",
  },
};
