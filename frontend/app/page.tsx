"use client";

import { useEffect, useRef, useState } from "react";
import { AboutPanel } from "@/components/AboutPanel";
import { AppHeader } from "@/components/AppHeader";
import { DigestBrief } from "@/components/DigestBrief";
import { DigestList } from "@/components/DigestList";
import { EvidencePanel } from "@/components/EvidencePanel";
import { HistoryPanel } from "@/components/HistoryPanel";
import { WatchlistManager, type WatchlistManagerHandle } from "@/components/WatchlistManager";
import { useDigest } from "@/hooks/useDigest";
import { useProviderStatus } from "@/hooks/useProviderStatus";
import { ackFlags, fetchEvidence, listTickers } from "@/lib/api";
import { ensureBootstrapWatchlist } from "@/lib/bootstrap";
import { EMPTY_DIGEST_POLL_STATE, newFlagIds, type DigestPollState } from "@/lib/digestPoll";
import type { EvidenceResponse, Flag, TickerInfo } from "@/lib/types";

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

  const [aboutOpen, setAboutOpen] = useState(false);
  const [historyTarget, setHistoryTarget] = useState<{ ticker: string; name: string } | null>(null);

  const [ackedCount, setAckedCount] = useState(0);

  // Real ticker metadata (name/sector), keyed by ticker — Flag rows don't
  // carry these, so it's cross-referenced from the real universe once.
  const [tickerInfo, setTickerInfo] = useState<Record<string, TickerInfo>>({});
  useEffect(() => {
    listTickers()
      .then((tickers) => setTickerInfo(Object.fromEntries(tickers.map((t) => [t.ticker, t]))))
      .catch(() => {
        // Non-critical — rows just fall back to ticker-only display.
      });
  }, []);

  const watchlistManagerRef = useRef<WatchlistManagerHandle>(null);

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
    setAckedCount((n) => n + 1);
    // Server is authoritative — refetch rather than optimistically mutate.
    // The hash just changed, so this poll gets a real 200, not a stale 304.
    const fresh = await pollOnce();
    setViewed(fresh);
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-8 sm:px-6">
      <AppHeader
        onAboutClick={() => setAboutOpen(true)}
        onAddStockClick={() => watchlistManagerRef.current?.focusSearch()}
        providerStatus={providerStatus}
        onFaultChanged={() => pollOnce()}
      />

      <DigestBrief brief={viewed.data?.brief ?? null} flags={viewed.data?.flags ?? null} ackedCount={ackedCount} />

      {bootstrapError && (
        <div className="rounded-md bg-down-wash px-3 py-2 text-sm text-down-text">{bootstrapError}</div>
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-4">
          <DigestList
            flags={viewed.data?.flags ?? null}
            events={viewed.data?.events}
            error={digestError}
            selectedFlagId={selectedFlag?.id}
            pendingNewCount={pendingNewCount}
            tickerInfo={tickerInfo}
            onPullInNew={() => setViewed(latest)}
            onAck={handleAck}
            onSelect={handleSelect}
          />
        </div>

        <div className="flex flex-col gap-4">
          {watchlistId && (
            <WatchlistManager
              ref={watchlistManagerRef}
              watchlistId={watchlistId}
              onViewHistory={(ticker, name) => setHistoryTarget({ ticker, name })}
            />
          )}
        </div>
      </div>

      {selectedFlag && (
        <EvidencePanel
          flag={selectedFlag}
          evidence={evidence}
          loading={evidenceLoading}
          error={evidenceError}
          onAck={handleAck}
          onClose={() => setSelectedFlag(null)}
        />
      )}

      {aboutOpen && <AboutPanel onClose={() => setAboutOpen(false)} />}

      {historyTarget && (
        <HistoryPanel
          ticker={historyTarget.ticker}
          name={historyTarget.name}
          onClose={() => setHistoryTarget(null)}
        />
      )}
    </div>
  );
}
