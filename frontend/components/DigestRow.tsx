"use client";

import { useEffect, useState } from "react";
import { ACK_DWELL_MS, scheduleDwellAck } from "@/lib/dwell";
import { explainFlag } from "@/lib/explain";
import type { Flag } from "@/lib/types";
import { SeverityBadge } from "./SeverityBadge";

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

  return (
    <li className="flex items-start justify-between gap-3 border-b border-zinc-100 px-3 py-3 last:border-0 dark:border-zinc-800">
      <button
        onClick={() => onSelect(flag)}
        className="flex flex-1 flex-col items-start gap-1 text-left"
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold text-zinc-900 dark:text-zinc-50">{bareTicker}</span>
          <SeverityBadge severity={flag.severity} />
        </div>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">{explainFlag(flag)}</p>
        <span className="text-xs text-zinc-400">
          {new Date(flag.computed_at).toLocaleString()}
        </span>
      </button>
      <button
        onClick={() => onAck(flag.id)}
        disabled={!ackEligible}
        title={ackEligible ? "Acknowledge" : "Reviewing…"}
        className="mt-1 rounded-full border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-30 dark:border-zinc-700 dark:text-zinc-300"
      >
        ✓ Ack
      </button>
    </li>
  );
}
