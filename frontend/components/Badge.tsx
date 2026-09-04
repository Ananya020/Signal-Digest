import type { BadgeConfig } from "@/lib/severity";

/** Freshness state indicator — design.md reserves full (pill) rounding
 * specifically for live connection pings / status dots, unlike the
 * severity marks in the digest (rounded-sm chips, never full pills).
 * Renders color + icon + text label together, always — color is never
 * the sole signal. */
export function Badge({ config, size = "sm" }: { config: BadgeConfig; size?: "sm" | "md" }) {
  const padding = size === "md" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${padding} ${config.bgClass} ${config.textClass}`}>
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
}
