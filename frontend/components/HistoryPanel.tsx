"use client";

import { useEffect, useState } from "react";
import { fetchTickerFlags } from "@/lib/api";
import { directionFromFlag, SEVERITY_META } from "@/lib/severity";
import type { HistoricalFlag } from "@/lib/types";
import { Dialog } from "./Dialog";

const SIGNAL_LABEL: Record<HistoricalFlag["signal_type"], string> = {
  price_zscore: "Price anomaly",
  volatility_regime: "Volatility regime",
};

function formatTradingDay(isoDate: string): string {
  // isoDate is a plain YYYY-MM-DD (no time component) — parse as UTC so the
  // viewer's own timezone can never shift it to the adjacent calendar day.
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    timeZone: "UTC",
  });
}

/** The ticker's real, queryable flags audit trail — proves the `flags`
 * table is a genuine history, not just "whatever's currently unacked."
 * Deliberately minimal (design.md): edge-to-edge rows, hairline dividers,
 * tabular numerals, no charts/cards/summary stats. Fetches real backend
 * data on open — never derives history from the current digest state, so a
 * ticker with zero active signals can still show past flags here. */
export function HistoryPanel({
  ticker,
  name,
  onClose,
}: {
  ticker: string;
  name?: string;
  onClose: () => void;
}) {
  const [flags, setFlags] = useState<HistoricalFlag[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setFlags(null);
    setError(null);
    fetchTickerFlags(ticker)
      .then((data) => {
        if (!cancelled) setFlags(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load history");
      });
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  const bareTicker = ticker.replace(/\.NS$/, "");

  return (
    <Dialog onClose={onClose} labelledBy="history-panel-title">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 id="history-panel-title" className="text-sm font-semibold text-ink">
            Historical changes
          </h2>
          <p className="text-xs text-ink-muted">
            {bareTicker}
            {name ? ` · ${name}` : ""}
          </p>
        </div>
        <button onClick={onClose} className="focus-ring rounded text-ink-muted hover:text-ink" aria-label="Close">
          ✕
        </button>
      </div>

      {error && <p className="py-8 text-center text-sm text-down-text">Couldn&apos;t load history: {error}</p>}

      {!error && flags === null && <p className="py-8 text-center text-sm text-ink-muted">Loading…</p>}

      {!error && flags !== null && flags.length === 0 && (
        <p className="py-8 text-center text-sm text-ink-muted">
          Nothing unusual has been recorded for this ticker.
        </p>
      )}

      {!error && flags !== null && flags.length > 0 && (
        <ul className="max-h-[60vh] overflow-y-auto">
          {flags.map((flag, i) => {
            const meta = SEVERITY_META[flag.severity];
            const direction = flag.z_score != null ? directionFromFlag(flag) : null;
            return (
              <li
                key={`${flag.trading_day}-${flag.signal_type}-${i}`}
                className="flex items-center justify-between gap-3 border-b border-hairline py-2.5 last:border-0"
              >
                <span className="tnum text-xs text-ink-muted">{formatTradingDay(flag.trading_day)}</span>
                <div className="flex flex-col items-end gap-0.5">
                  <span className="flex items-center gap-1.5 text-xs font-medium text-ink">
                    <span aria-hidden="true">{meta.icon}</span>
                    {meta.label.toUpperCase()}
                    {flag.z_score != null && (
                      <span
                        className={`tnum ${direction === "up" ? "text-up-text" : "text-down-text"}`}
                      >
                        {flag.z_score > 0 ? "+" : ""}
                        {flag.z_score.toFixed(2)}σ
                      </span>
                    )}
                  </span>
                  <span className="label-caps text-ink-muted">{SIGNAL_LABEL[flag.signal_type]}</span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Dialog>
  );
}
