"use client";

import { useEffect, useRef, useState } from "react";
import { fetchProviderStatus } from "@/lib/api";
import type { ProviderStatus } from "@/lib/types";

/** Polls faster than the backend's default 5s scheduler cadence so the
 * freshness banner's age_seconds/state transitions feel responsive. */
export const PROVIDER_STATUS_POLL_MS = 3000;

export function useProviderStatus(intervalMs: number = PROVIDER_STATUS_POLL_MS) {
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    async function poll() {
      try {
        const s = await fetchProviderStatus();
        if (!cancelledRef.current) setStatus(s);
      } catch {
        // transient network hiccup — keep showing the last known status
        // rather than flashing an error banner on every missed poll.
      }
    }

    poll();
    const id = setInterval(poll, intervalMs);
    return () => {
      cancelledRef.current = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return status;
}
