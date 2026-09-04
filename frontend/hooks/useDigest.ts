"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchDigest } from "@/lib/api";
import { applyDigestPollResult, EMPTY_DIGEST_POLL_STATE, type DigestPollState } from "@/lib/digestPoll";

/** Matches the backend's default scheduler cadence — new flags can't
 * appear faster than that anyway, so polling faster would just add load
 * without more real-time information. */
export const DIGEST_POLL_MS = 5000;

export function useDigest(watchlistId: string | null, intervalMs: number = DIGEST_POLL_MS) {
  const [latest, setLatest] = useState<DigestPollState>(EMPTY_DIGEST_POLL_STATE);
  const [error, setError] = useState<string | null>(null);
  const latestRef = useRef(latest);
  latestRef.current = latest;

  const pollOnce = useCallback(async (): Promise<DigestPollState> => {
    if (!watchlistId) return latestRef.current;
    try {
      const result = await fetchDigest(watchlistId, latestRef.current.etag);
      const next = applyDigestPollResult(latestRef.current, result);
      setLatest(next);
      setError(null);
      return next;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load digest");
      return latestRef.current;
    }
  }, [watchlistId]);

  useEffect(() => {
    if (!watchlistId) return;
    let cancelled = false;

    async function tick() {
      if (!cancelled) await pollOnce();
    }
    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [watchlistId, intervalMs, pollOnce]);

  return { latest, error, pollOnce };
}
