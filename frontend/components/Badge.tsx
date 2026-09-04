import type { BadgeConfig } from "@/lib/severity";

/** Renders color + icon + text label together, always — the accessibility
 * requirement (Stage 5) that color is never the sole signal. Both
 * SeverityBadge and FreshnessBanner render through this single component
 * so that guarantee lives in one place. */
export function Badge({ config, size = "sm" }: { config: BadgeConfig; size?: "sm" | "md" }) {
  const padding = size === "md" ? "px-3 py-1.5 text-sm" : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${padding} ${config.bgClass} ${config.textClass} ${config.borderClass}`}
    >
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
}
