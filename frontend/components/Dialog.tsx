"use client";

import { useEffect, useRef } from "react";

/** Shared accessible dialog shell for small, non-blocking product panels
 * (About, History) — role="dialog"/aria-modal, Escape closes, backdrop
 * click closes, a click inside the panel never reaches the backdrop (so it
 * can never trigger an accidental background action, e.g. a digest row's
 * Acknowledge button sitting behind it). Not a full focus-trap — panels
 * using this are small (a close button plus a short list/text), so moving
 * focus into the panel on open and returning it to the trigger on close is
 * sufficient without pulling in a dependency. */
export function Dialog({
  onClose,
  labelledBy,
  children,
  maxWidthClass = "max-w-md",
}: {
  onClose: () => void;
  labelledBy: string;
  children: React.ReactNode;
  maxWidthClass?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused.current?.focus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/30 p-4" onClick={onClose}>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className={`animate-panel-in w-full ${maxWidthClass} rounded-lg border border-border-strong bg-surface-raised p-4 shadow-[0_12px_32px_-4px_rgba(15,23,42,0.06),0_4px_8px_-2px_rgba(15,23,42,0.03)] focus:outline-none`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
