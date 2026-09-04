"use client";

import { useState } from "react";
import { setFaultMode } from "@/lib/api";
import type { FaultMode, ProviderStatus } from "@/lib/types";

/** Only rendered by the caller when status.demo_mode is true — never
 * guessed/hardcoded client-side. Internal state (mode, frozen_at, replay
 * step) is shown here specifically — useful for live narration — and kept
 * out of the main freshness banner, which speaks in user-facing language
 * only. Buttons use design.md's neutral Secondary/Ghost treatment: these
 * are admin utility actions, not price signals, so they deliberately stay
 * outside the direction/severity color vocabulary. */
export function FaultControl({ status, onChanged }: { status: ProviderStatus | null; onChanged: () => void }) {
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
    <div className="flex flex-col gap-2 rounded-md border border-dashed border-border bg-surface-subtle px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <span className="label-caps text-ink-muted">Demo controls</span>
        <div className="flex gap-1.5">
          <button
            onClick={() => trigger("outage")}
            disabled={pending !== null}
            className="rounded-md border border-border bg-surface-raised px-2.5 py-1 text-xs font-medium text-ink transition-colors hover:bg-surface-subtle disabled:opacity-50"
          >
            {pending === "outage" ? "Setting…" : "Outage"}
          </button>
          <button
            onClick={() => trigger("stale")}
            disabled={pending !== null}
            className="rounded-md border border-border bg-surface-raised px-2.5 py-1 text-xs font-medium text-ink transition-colors hover:bg-surface-subtle disabled:opacity-50"
          >
            {pending === "stale" ? "Setting…" : "Stale"}
          </button>
          <button
            onClick={() => trigger("recover")}
            disabled={pending !== null}
            className="rounded-md border border-border bg-surface-raised px-2.5 py-1 text-xs font-medium text-ink transition-colors hover:bg-surface-subtle disabled:opacity-50"
          >
            {pending === "recover" ? "Setting…" : "Recover"}
          </button>
        </div>
      </div>
      {status && <p className="tnum font-mono text-[11px] text-ink-muted">{status.detail}</p>}
      {error && <span className="text-xs text-down-text">{error}</span>}
    </div>
  );
}
