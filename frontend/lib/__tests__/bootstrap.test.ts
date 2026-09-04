import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import { ensureBootstrapWatchlist, STARTER_TICKERS } from "../bootstrap";

vi.mock("../api");

describe("ensureBootstrapWatchlist", () => {
  beforeEach(() => vi.resetAllMocks());

  it("creates a watchlist and seeds starter tickers only when none exist", async () => {
    vi.mocked(api.listWatchlists).mockResolvedValue([]);
    vi.mocked(api.createWatchlist).mockResolvedValue({ id: "wl-1", user_id: "u1", name: "My Watchlist" });
    vi.mocked(api.addWatchlistItem).mockResolvedValue(undefined);

    const id = await ensureBootstrapWatchlist();

    expect(id).toBe("wl-1");
    expect(api.createWatchlist).toHaveBeenCalledTimes(1);
    expect(api.addWatchlistItem).toHaveBeenCalledTimes(STARTER_TICKERS.length);
  });

  it("never creates a duplicate when a watchlist already exists", async () => {
    vi.mocked(api.listWatchlists).mockResolvedValue([
      { id: "existing-wl", name: "My Watchlist", created_at: "2026-01-01T00:00:00Z" },
    ]);

    const id = await ensureBootstrapWatchlist();

    expect(id).toBe("existing-wl");
    expect(api.createWatchlist).not.toHaveBeenCalled();
    expect(api.addWatchlistItem).not.toHaveBeenCalled();
  });
});
