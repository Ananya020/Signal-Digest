"use client";

import { Dialog } from "./Dialog";

/** Product-information panel, not a marketing page. Content is drawn
 * directly from PRODUCT.md's locked decisions — no invented claims, no
 * predictive/investment-advice language, no overstated real-time framing
 * (this build replays real historical data on a clock, it does not stream
 * live market prices). */
export function AboutPanel({ onClose }: { onClose: () => void }) {
  return (
    <Dialog onClose={onClose} labelledBy="about-panel-title" maxWidthClass="max-w-lg">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="about-panel-title" className="text-sm font-semibold text-ink">
          About this build
        </h2>
        <button onClick={onClose} className="focus-ring rounded text-ink-muted hover:text-ink" aria-label="Close">
          ✕
        </button>
      </div>

      <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-muted">
        <p>
          Signal Digest flags price and volume moves that are statistically unusual for a specific
          instrument&apos;s own recent behavior — not a flat percentage threshold. Every flag ships with the
          reasoning behind it: a z-score against that instrument&apos;s own rolling baseline, volume context, and
          whether the move was sector-wide or stock-specific.
        </p>
        <p>
          A conventional watchlist judges every row against the same threshold. A 2% move means something
          different for a stable large-cap than a volatile mid-cap — this compares each move to that
          instrument&apos;s own normal behavior instead of a one-size-fits-all number.
        </p>
        <p>
          Scoring is fully deterministic: a z-score crossing is the sole trigger, with volume and sector
          context kept as annotations, never blended into one composite score. No ML or LLM sits in the
          decision path — a defensible number plus plain English beats justifying arbitrary model weights.
        </p>
        <p>
          The product&apos;s core mechanic is &quot;what changed since you last checked,&quot; not just what&apos;s
          true right now — modeled on two real Groww engineering posts: <em>Improving the Efficiency of
          Rendering User Holdings</em> (the ETag/304 short-circuit this digest&apos;s polling is built on) and{" "}
          <em>Holding Revamp Went Live. Then Reality Check Hit Hard</em> (the cache-invalidation postmortem
          this project&apos;s same-transaction ack-bust rule was built to avoid).
        </p>
        <p className="border-t border-hairline pt-3 text-xs text-ink-muted">
          This build replays real historical price data on a clock, not a live market feed, and does not
          provide investment advice.
        </p>
      </div>
    </Dialog>
  );
}
