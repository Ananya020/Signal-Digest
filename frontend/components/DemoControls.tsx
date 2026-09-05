"use client";

import { useEffect, useRef, useState } from "react";
import { FlaskConical } from "lucide-react";
import { setFaultMode } from "@/lib/api";
import type { FaultMode, ProviderStatus } from "@/lib/types";

const MODES: { mode: FaultMode; label: string; hint: string }[] = [
  { mode: "outage", label: "Inject outage", hint: "Provider returns nothing" },
  { mode: "stale", label: "Inject stale data", hint: "Feed stops refreshing" },
  { mode: "recover", label: "Recover", hint: "Return to live updates" },
];

/** Discreet demo-only fault injection, restyled to ui_reference.md's
 * DemoControls popover — only ever rendered by the caller when
 * status.demo_mode is true (see AppHeader), never guessed/hardcoded here.
 * This gating doesn't exist in the reference (it has no concept of a
 * non-demo build) — added, not lost, per this step's instructions. */
export function DemoControls({ status, onChanged }: { status: ProviderStatus | null; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<FaultMode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

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
    <div ref={rootRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Demo controls"
        aria-expanded={open}
        className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
      >
        <FlaskConical className="size-4" aria-hidden="true" />
        <span className="hidden sm:inline">Demo</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full z-40 mt-2 w-64 rounded-lg border border-border-strong bg-surface-raised p-3 shadow-[0_12px_32px_-4px_rgba(15,23,42,0.06),0_4px_8px_-2px_rgba(15,23,42,0.03)]">
          <p className="eyebrow">Demo controls</p>
          <p className="mt-1.5 text-xs text-ink-muted">
            Fault injection for the demo build only. Simulates provider degradation.
          </p>
          <div className="mt-3 grid gap-1.5">
            {MODES.map(({ mode, label, hint }) => (
              <button
                key={mode}
                onClick={() => trigger(mode)}
                disabled={pending !== null}
                className="focus-ring flex flex-col items-start gap-0.5 rounded-md px-2 py-2 text-left transition-colors hover:bg-surface-subtle disabled:opacity-50"
              >
                <span className="text-xs font-medium text-ink">{pending === mode ? "Setting…" : label}</span>
                <span className="text-[11px] text-ink-muted">{hint}</span>
              </button>
            ))}
          </div>
          {status && <p className="tnum mt-2 font-mono text-[11px] text-ink-muted">{status.detail}</p>}
          {error && <p className="mt-1 text-xs text-down-text">{error}</p>}
        </div>
      )}
    </div>
  );
}
