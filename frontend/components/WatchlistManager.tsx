"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { History, Plus, Search, Trash2 } from "lucide-react";
import { addWatchlistItem, listTickers, listWatchlistItems, removeWatchlistItem } from "@/lib/api";
import type { TickerInfo } from "@/lib/types";

/** Search/select to add a ticker plus a flat, removable list of current
 * membership, restyled to ui_reference.md's WatchlistPanel shell (card
 * container, live search-as-you-type, icon-button row actions). History
 * still opens the existing real History dialog (`onViewHistory`,
 * GET /tickers/{ticker}/flags) — that content itself is wired in its own
 * later step. Digest polling already picks up membership changes on its
 * own interval — this component never forces a digest refresh itself. */
export function WatchlistManager({
  watchlistId,
  onViewHistory,
}: {
  watchlistId: string;
  onViewHistory: (ticker: string, name: string) => void;
}) {
  const [items, setItems] = useState<TickerInfo[] | null>(null);
  const [universe, setUniverse] = useState<TickerInfo[] | null>(null);
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    try {
      setItems(await listWatchlistItems(watchlistId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load watchlist items");
    }
  }, [watchlistId]);

  useEffect(() => {
    loadItems();
    listTickers()
      .then(setUniverse)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load ticker universe"));
  }, [loadItems]);

  const currentTickers = new Set((items ?? []).map((i) => i.ticker));
  const available = (universe ?? []).filter((t) => !currentTickers.has(t.ticker));

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 1) return [];
    return available
      .filter((t) => t.ticker.toLowerCase().includes(q) || t.name.toLowerCase().includes(q))
      .slice(0, 5);
  }, [query, available]);

  async function handleAdd(ticker: string) {
    setPending(true);
    setError(null);
    try {
      await addWatchlistItem(watchlistId, ticker);
      setQuery("");
      await loadItems();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add ticker");
    } finally {
      setPending(false);
    }
  }

  async function handleRemove(ticker: string) {
    setPending(true);
    setError(null);
    try {
      await removeWatchlistItem(watchlistId, ticker);
      await loadItems();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove ticker");
    } finally {
      setPending(false);
    }
  }

  return (
    <section
      aria-labelledby="watchlist-heading"
      className="rounded-xl border border-border bg-surface-raised shadow-[0_1px_2px_rgba(15,23,42,0.04)]"
    >
      <div className="flex items-center justify-between gap-3 border-b border-hairline px-4 py-3">
        <h2 id="watchlist-heading" className="eyebrow">
          Watchlist
        </h2>
        <span className="num text-xs text-ink-muted">{items?.length ?? 0} tracked</span>
      </div>

      <div className="border-b border-hairline px-4 py-3">
        <label className="relative block">
          <span className="sr-only">Search stocks to add</span>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted"
            aria-hidden="true"
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={pending}
            placeholder="Add a stock — e.g. TITAN"
            className="focus-ring h-10 w-full rounded-md border border-border bg-surface-raised pl-9 pr-3 text-sm text-ink disabled:opacity-50"
          />
        </label>
        {results.length > 0 && (
          <ul className="mt-2 divide-y divide-hairline overflow-hidden rounded-lg border border-border">
            {results.map((r) => (
              <li key={r.ticker} className="flex items-center justify-between gap-3 px-3 py-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">{r.ticker.replace(/\.NS$/, "")}</p>
                  <p className="truncate text-xs text-ink-muted">
                    {r.name} · {r.sector}
                  </p>
                </div>
                <button
                  onClick={() => handleAdd(r.ticker)}
                  disabled={pending}
                  className="focus-ring inline-flex shrink-0 items-center gap-1 rounded-md bg-surface-subtle px-2.5 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-border disabled:opacity-50"
                >
                  <Plus className="size-4" aria-hidden="true" /> Add
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {items === null ? (
        <p className="px-4 py-8 text-center text-sm text-ink-muted">Loading…</p>
      ) : items.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-ink-muted">
          Your watchlist is empty. Search above to start tracking a stock.
        </p>
      ) : (
        <ul className="divide-y divide-hairline">
          {items.map((item) => (
            <li
              key={item.ticker}
              className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-hover"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink">{item.ticker.replace(/\.NS$/, "")}</p>
                <p className="truncate text-xs text-ink-muted">
                  {item.name} · {item.sector}
                </p>
              </div>
              <button
                onClick={() => onViewHistory(item.ticker, item.name)}
                aria-label={`View signal history for ${item.ticker}`}
                title="View history"
                className="focus-ring rounded-md p-1.5 text-ink-muted transition-colors hover:bg-surface-subtle hover:text-cobalt"
              >
                <History className="size-4" aria-hidden="true" />
              </button>
              <button
                onClick={() => handleRemove(item.ticker)}
                disabled={pending}
                aria-label={`Remove ${item.ticker} from watchlist`}
                title="Remove"
                className="focus-ring rounded-md p-1.5 text-ink-muted transition-colors hover:bg-down-wash hover:text-down-text disabled:opacity-50"
              >
                <Trash2 className="size-4" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="px-4 pb-3 text-xs text-down-text">{error}</p>}
    </section>
  );
}
