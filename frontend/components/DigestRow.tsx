"use client";

import { useEffect, useState } from "react";
import { ACK_DWELL_MS, scheduleDwellAck } from "@/lib/dwell";
import { explainFlag } from "@/lib/explain";
import { directionFromFlag, resolveRowStyle } from "@/lib/severity";
import type { Flag } from "@/lib/types";

export function DigestRow({
  flag,
  onAck,
  onSelect,
}: {
  flag: Flag;
  onAck: (flagId: number) => void;
  onSelect: (flag: Flag) => void;
}) {
  // Stage 2 design: ack becomes eligible only after a short dwell on the
  // rendered row, not on mount — prevents an accidental instant-dismiss the
  // moment a fresh digest renders.
  const [ackEligible, setAckEligible] = useState(false);

  useEffect(() => {
    setAckEligible(false);
    const cancel = scheduleDwellAck(ACK_DWELL_MS, () => setAckEligible(true));
    return cancel;
  }, [flag.id]);

  const bareTicker = flag.ticker.replace(/\.NS$/, "");
  const direction = directionFromFlag(flag);
  const style = resolveRowStyle(flag.severity, direction);
  const time = new Date(flag.computed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <li
      className={`animate-row-in flex flex-col gap-1.5 border-b border-hairline px-4 py-3 last:border-0 ${style.barWidthClass} ${style.barColorClass} ${style.rowBgClass}`}
    >
      <div className="flex items-start justify-between gap-3">
        <button onClick={() => onSelect(flag)} className="flex min-w-0 items-center gap-2 text-left">
          <span className={`${style.tickerWeightClass} text-ink`}>{bareTicker}</span>
          <span
            className={`inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium ${style.badgeBgClass} ${style.badgeTextClass}`}
          >
            <span aria-hidden="true">{style.icon}</span>
            {style.label}
          </span>
        </button>
        <time className="tnum shrink-0 pt-0.5 text-xs text-ink-muted">{time}</time>
      </div>

      <button onClick={() => onSelect(flag)} className="text-left">
        <p className="tnum text-sm text-ink-muted">
          <span aria-hidden="true" className={style.arrowTextClass}>
            {style.arrow}{" "}
          </span>
          {explainFlag(flag)}
        </p>
      </button>

      <button
        onClick={() => onAck(flag.id)}
        disabled={!ackEligible}
        title={ackEligible ? "Acknowledge this signal" : "Reviewing…"}
        className="self-start rounded px-1.5 py-1 text-xs font-medium text-ink-muted transition-colors hover:text-ink disabled:cursor-not-allowed disabled:opacity-30"
      >
        Acknowledge
      </button>
    </li>
  );
}
