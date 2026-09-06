import type { Flag } from "@/lib/types";

/** "Today's Brief" — a short intelligence summary, restyled to
 * ui_reference.md's TodaysBrief (eyebrow + large headline + a real stats
 * row), but the headline sentence itself is still rendered verbatim from
 * the real deterministic backend field (`backend/app/services/brief.py`)
 * — the reference's own client-side sentence-generation logic (built from
 * count/strongest/stockSpecific/sectorWide) is discarded, never
 * regenerated here, per PRODUCT.md's "deterministic template is the
 * default and final target" decision.
 *
 * Renders nothing when there's no brief text (zero active signals): the
 * digest's existing empty-state copy already covers that case, so this
 * never renders a second, duplicate "nothing unusual" line of its own.
 *
 * `ackedCount` is a real count of acks made this session (see
 * app/page.tsx's `handleAck`) — not the server-authoritative all-time
 * count the reference's stat implies, since the digest only ever returns
 * currently-unacked flags and there's no endpoint for a running total.
 * Labeled "this session" so that distinction is never implied to be more
 * than it is; omitted entirely at 0 rather than shown as a bare zero. */
export function DigestBrief({
  brief,
  flags,
  ackedCount,
}: {
  brief: string | null;
  flags: Flag[] | null;
  ackedCount: number;
}) {
  if (!brief) return null;

  const stockSpecific = (flags ?? []).filter((f) => f.sector_relative === "stock_specific").length;
  const sectorWide = (flags ?? []).filter((f) => f.sector_relative === "sector_wide").length;

  return (
    <section data-tour="brief" aria-labelledby="brief-heading" className="flex flex-col gap-3 border-b border-hairline pb-5">
      <h2 id="brief-heading" className="eyebrow">
        Today
      </h2>
      <p className="max-w-3xl font-display text-xl leading-snug tracking-tight text-ink sm:text-2xl">{brief}</p>
      <dl className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-ink-muted">
        <div className="flex items-baseline gap-1.5">
          <dd className="num font-semibold text-ink">{stockSpecific}</dd>
          <dt>stock-specific</dt>
        </div>
        <div className="flex items-baseline gap-1.5">
          <dd className="num font-semibold text-ink">{sectorWide}</dd>
          <dt>sector-wide</dt>
        </div>
        {ackedCount > 0 && (
          <div className="flex items-baseline gap-1.5">
            <dd className="num font-semibold text-ink">{ackedCount}</dd>
            <dt>acknowledged this session</dt>
          </div>
        )}
        <span className="text-xs">Threshold |z| ≥ 2.0 vs. each stock&apos;s own 30-day behavior</span>
      </dl>
    </section>
  );
}
