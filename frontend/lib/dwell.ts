/** Schedules `callback` to fire after `delayMs` of the row staying rendered
 * (Stage 2's "ack on confirmed render + short dwell" design — not on
 * mount). Returns a cancel function; call it on unmount/re-render/if the
 * row changes before the dwell completes, so a flag scrolled past quickly
 * never gets acked. Pure wrapper around setTimeout so it's testable with
 * fake timers, independent of any React hook plumbing. */
export function scheduleDwellAck(delayMs: number, callback: () => void): () => void {
  const timer = setTimeout(callback, delayMs);
  return () => clearTimeout(timer);
}

export const ACK_DWELL_MS = 1500;
