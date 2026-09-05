"use client";

/** Product identity — a deliberate wordmark treatment, not a plain page
 * heading. Uses design.md's own headline scale steps (headline-md on
 * mobile, headline-lg on desktop) rather than inventing a new type size,
 * and the tagline is PRODUCT.md's own stated core user promise, verbatim —
 * not new positioning. */
export function AppHeader({ onAboutClick }: { onAboutClick: () => void }) {
  return (
    <header className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <div className="font-display flex items-baseline gap-0.5 text-[20px] font-semibold leading-[28px] tracking-[-0.015em] sm:text-[28px] sm:leading-[36px] sm:tracking-[-0.02em]">
          <span className="text-ink-muted">signal</span>
          <span className="text-ink">Digest</span>
        </div>
        <button
          onClick={onAboutClick}
          className="focus-ring shrink-0 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
        >
          About
        </button>
      </div>
      <p className="text-sm text-ink-muted">
        Know in five seconds what actually changed — not what always jitters — and why.
      </p>
    </header>
  );
}
