import { resolveRowStyle, type Direction } from "@/lib/severity";
import type { Severity } from "@/lib/types";

/** Severity (intensity/weight) and direction (hue) are always resolved
 * together — color is never severity-alone, per design.md's two-channel
 * rule. */
export function SeverityBadge({ severity, direction }: { severity: Severity; direction: Direction }) {
  const style = resolveRowStyle(severity, direction);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium ${style.badgeBgClass} ${style.badgeTextClass}`}
    >
      <span aria-hidden="true">{style.icon}</span>
      <span>{style.label}</span>
    </span>
  );
}
