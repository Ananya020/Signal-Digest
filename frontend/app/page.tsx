"use client";

import { useEffect, useRef, useState } from "react";
import { DigestList } from "@/components/DigestList";
import { EvidencePanel } from "@/components/EvidencePanel";
import { FaultControl } from "@/components/FaultControl";
import { FreshnessBanner } from "@/components/FreshnessBanner";
import { useDigest } from "@/hooks/useDigest";
import { useProviderStatus } from "@/hooks/useProviderStatus";
import { ackFlags, fetchEvidence } from "@/lib/api";
import { ensureBootstrapWatchlist } from "@/lib/bootstrap";
import { EMPTY_DIGEST_POLL_STATE, newFlagIds, type DigestPollState } from "@/lib/digestPoll";
import type { EvidenceResponse, Flag } from "@/lib/types";

export default function Home() {
  const [watchlistId, setWatchlistId] = useState<string | null>(null);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  const bootstrapStarted = useRef(false);

  useEffect(() => {
    if (bootstrapStarted.current) return; // guards React StrictMode's double-invoke in dev
    bootstrapStarted.current = true;
    ensureBootstrapWatchlist()
      .then(setWatchlistId)
      .catch((e) => setBootstrapError(e instanceof Error ? e.message : "Failed to set up watchlist"));
  }, []);

  const providerStatus = useProviderStatus();
  const { latest, error: digestError, pollOnce } = useDigest(watchlistId);

  // What's actually rendered — distinct from `latest` so a background poll
  // revealing new flags doesn't silently rewrite the list the user is
  // looking at (Stage 2 requirement).
  const [viewed, setViewed] = useState<DigestPollState>(EMPTY_DIGEST_POLL_STATE);
  const firstLoadDone = useRef(false);

  useEffect(() => {
    if (!firstLoadDone.current && latest.data) {
      setViewed(latest);
      firstLoadDone.current = true;
    }
  }, [latest]);

  const pendingNewCount = firstLoadDone.current ? newFlagIds(viewed, latest).length : 0;

  const [selectedFlag, setSelectedFlag] = useState<Flag | null>(null);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);

  async function handleSelect(flag: Flag) {
    setSelectedFlag(flag);
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(true);
    try {
      const data = await fetchEvidence(flag.ticker, flag.id);
      setEvidence(data);
    } catch (e) {
      setEvidenceError(e instanceof Error ? e.message : "Failed to load evidence");
    } finally {
      setEvidenceLoading(false);
    }
  }

  async function handleAck(flagId: number) {
    if (!watchlistId) return;
    await ackFlags(watchlistId, [flagId]);
    // Server is authoritative — refetch rather than optimistically mutate.
    // The hash just changed, so this poll gets a real 200, not a stale 304.
    const fresh = await pollOnce();
    setViewed(fresh);
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 p-4 sm:p-8">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Signal Digest</h1>

      {bootstrapError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {bootstrapError}
        </div>
      )}

      <FreshnessBanner status={providerStatus} />

      {providerStatus?.demo_mode && (
        <FaultControl onChanged={() => pollOnce()} />
      )}

      <DigestList
        flags={viewed.data?.flags ?? null}
        error={digestError}
        pendingNewCount={pendingNewCount}
        onPullInNew={() => setViewed(latest)}
        onAck={handleAck}
        onSelect={handleSelect}
      />

      {selectedFlag && (
        <EvidencePanel
          evidence={evidence}
          loading={evidenceLoading}
          error={evidenceError}
          onClose={() => setSelectedFlag(null)}
        />
      )}
    </div>
  );
}
