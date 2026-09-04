"use client";

import { useCallback, useEffect, useState } from "react";
import { addWatchlistItem, listTickers, listWatchlistItems, removeWatchlistItem } from "@/lib/api";
import type { TickerInfo } from "@/lib/types";

/** Utility screen, not a hero screen — a simple search/select to add a
 * ticker plus a flat remove-able list of current membership. Uses
 * design.md's existing tokens (surface-subtle panel, hairline row
 * dividers) rather than a distinct visual style. Digest polling already
 * picks up membership changes on its own interval — this component never
 * forces a digest refresh itself. */
export function WatchlistManager({ watchlistId }: { watchlistId: string }) {
  const [items, setItems] = useState<TickerInfo[] | null>(null);
  const [universe, setUniverse] = useState<TickerInfo[] | null>(null);
  const [selected, setSelected] = useState("");
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

  async function handleAdd() {
    if (!selected) return;
    setPending(true);
    setError(null);
    try {
      await addWatchlistItem(watchlistId, selected);
      setSelected("");
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
    <div className="flex flex-col gap-2 rounded-md bg-surface-subtle px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <span className="label-caps text-ink-muted">Watchlist</span>
        <div className="flex items-center gap-1.5">
          <select
            aria-label="Add a ticker to your watchlist"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            disabled={pending || available.length === 0}
            className="rounded-md border border-border bg-surface-raised px-2 py-1 text-xs text-ink disabled:opacity-50"
          >
            <option value="">Add ticker…</option>
            {available.map((t) => (
              <option key={t.ticker} value={t.ticker}>
                {t.ticker.replace(/\.NS$/, "")} — {t.name}
              </option>
            ))}
          </select>
          <button
            onClick={handleAdd}
            disabled={pending || !selected}
            className="rounded-md border border-border bg-surface-raised px-2.5 py-1 text-xs font-medium text-ink transition-colors hover:bg-surface-subtle disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>

      {items === null ? (
        <p className="text-xs text-ink-muted">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-xs text-ink-muted">No tickers yet.</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li
              key={item.ticker}
              className="flex items-center justify-between gap-2 border-b border-hairline py-1.5 last:border-0"
            >
              <span className="text-xs text-ink">
                {item.ticker.replace(/\.NS$/, "")} <span className="text-ink-muted">({item.sector})</span>
              </span>
              <button
                onClick={() => handleRemove(item.ticker)}
                disabled={pending}
                title={`Remove ${item.ticker}`}
                className="text-xs text-ink-muted transition-colors hover:text-down-text disabled:opacity-50"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <span className="text-xs text-down-text">{error}</span>}
    </div>
  );
}
