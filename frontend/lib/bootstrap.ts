import { addWatchlistItem, createWatchlist, listWatchlists } from "./api";

/** A small, recognizable starter set from the real seeded universe.
 * TATAMOTORS.NS is deliberately excluded — it failed Yahoo's backfill
 * (see PROGRESS.md) and doesn't exist in the `tickers` table, so adding it
 * would 422. */
export const STARTER_TICKERS = [
  "RELIANCE.NS",
  "TCS.NS",
  "INFY.NS",
  "HDFCBANK.NS",
  "ICICIBANK.NS",
  "MARUTI.NS",
  "ITC.NS",
];

/** Ensures exactly one watchlist exists for the demo user, seeded with the
 * starter tickers — only on the very first run. Checks for an existing
 * watchlist first; never creates a second one on a later call/reload. */
export async function ensureBootstrapWatchlist(): Promise<string> {
  const existing = await listWatchlists();
  if (existing.length > 0) {
    return existing[0].id;
  }

  const created = await createWatchlist("My Watchlist");
  await Promise.all(STARTER_TICKERS.map((ticker) => addWatchlistItem(created.id, ticker)));
  return created.id;
}
