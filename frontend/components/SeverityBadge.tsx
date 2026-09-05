import { AlertTriangle, ArrowDownRight, ArrowUpRight, CircleAlert, Info } from "lucide-react";
import { SEVERITY_META, type Direction } from "@/lib/severity";
import type { Severity } from "@/lib/types";

const STYLES: Record<Severity, string> = {
  notable: "bg-notable-soft text-notable border-notable/25",
  significant: "bg-significant-soft text-significant border-significant/30",
  extreme: "bg-extreme-soft text-extreme border-extreme/30",
};

const ICONS: Record<Severity, typeof Info> = {
  notable: Info,
  significant: CircleAlert,
  extreme: AlertTriangle,
};

/** Severity's own hue (never/amber/red) is always paired with an icon and
 * the text label — never color alone. Direction is a wholly separate cue
 * (see `DirectionArrow` below), not folded into this badge's color. */
export function SeverityBadge({ severity, className = "" }: { severity: Severity; className?: string }) {
  const Icon = ICONS[severity];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-display text-[11px] font-semibold uppercase tracking-[0.08em] ${STYLES[severity]} ${className}`}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {SEVERITY_META[severity].label}
    </span>
  );
}

/** Price direction, rendered as its own icon element — kept separate from
 * severity so severity's color scale and direction's cue never collide. */
export function DirectionArrow({ direction, className = "" }: { direction: Direction; className?: string }) {
  const Icon = direction === "up" ? ArrowUpRight : ArrowDownRight;
  return <Icon className={`size-4 ${className}`} aria-hidden="true" />;
}
