/** "Today's Brief" — a quiet, deterministic overview line, not the
 * dominant visual element. Renders nothing when there's no brief text (zero
 * active signals): the digest's existing empty-state copy ("Nothing unusual
 * right now. All caught up.") already covers that case — this component
 * must never render an empty/awkward line of its own. No icon, no "AI"
 * framing, no gradient/chat-bubble treatment — plain editorial text using
 * design.md's existing label-caps micro-label and body type. */
export function DigestBrief({ brief }: { brief: string | null }) {
  if (!brief) return null;

  return (
    <div className="flex flex-col gap-1">
      <span className="label-caps text-ink-muted">Today</span>
      <p className="text-sm text-ink">{brief}</p>
    </div>
  );
}
