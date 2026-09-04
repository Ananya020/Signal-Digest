import type { DigestPollResult } from "./api";
import type { DigestResponse } from "./types";

export interface DigestPollState {
  data: DigestResponse | null;
  etag: string | null;
}

export const EMPTY_DIGEST_POLL_STATE: DigestPollState = { data: null, etag: null };

/** Pure reducer for a single poll cycle — kept separate from the fetch call
 * itself so it's trivially unit-testable with a mocked DigestPollResult,
 * with no need to mock `fetch` or React state. A 304 (notModified) must
 * return a value equal to `prev` (same data/etag) — the caller keeps its
 * current state exactly, never overwritten by a stale/duplicate response. */
export function applyDigestPollResult(prev: DigestPollState, result: DigestPollResult): DigestPollState {
  if (result.notModified) {
    return prev;
  }
  return { data: result.data, etag: result.etag ?? prev.etag };
}

/** Flags present in `next` but not in `prev` — used to detect "new since
 * last render" without silently replacing what the user is looking at. */
export function newFlagIds(prev: DigestPollState, next: DigestPollState): number[] {
  if (!next.data) return [];
  const prevIds = new Set((prev.data?.flags ?? []).map((f) => f.id));
  return next.data.flags.filter((f) => !prevIds.has(f.id)).map((f) => f.id);
}
