"use client";

import { useState } from "react";
import { setFaultMode } from "@/lib/api";
import type { FaultMode } from "@/lib/types";

/** Only rendered by the caller when status.demo_mode is true — never
 * guessed/hardcoded client-side, per the backend's /provider/status
 * contract (see PROGRESS.md). */
export function FaultControl({ onChanged }: { onChanged: () => void }) {
  const [pending, setPending] = useState<FaultMode | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function trigger(mode: FaultMode) {
    setPending(mode);
    setError(null);
    try {
      await setFaultMode(mode);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to set fault mode");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex flex-col gap-1 rounded-md border border-dashed border-purple-300 bg-purple-50 px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-purple-700">
          Demo: fault injection
        </span>
        <div className="flex gap-1.5">
          <button
            onClick={() => trigger("outage")}
            disabled={pending !== null}
            className="rounded border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            {pending === "outage" ? "Setting…" : "Outage"}
          </button>
          <button
            onClick={() => trigger("stale")}
            disabled={pending !== null}
            className="rounded border border-orange-300 bg-white px-2 py-1 text-xs font-medium text-orange-700 hover:bg-orange-50 disabled:opacity-50"
          >
            {pending === "stale" ? "Setting…" : "Stale"}
          </button>
          <button
            onClick={() => trigger("recover")}
            disabled={pending !== null}
            className="rounded border border-green-300 bg-white px-2 py-1 text-xs font-medium text-green-700 hover:bg-green-50 disabled:opacity-50"
          >
            {pending === "recover" ? "Setting…" : "Recover"}
          </button>
        </div>
      </div>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
