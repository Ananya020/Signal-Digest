import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import { WatchlistManager } from "../WatchlistManager";

vi.mock("@/lib/api");

const UNIVERSE = [
  { ticker: "RELIANCE.NS", name: "Reliance Industries", sector: "Energy/Materials" },
  { ticker: "TCS.NS", name: "Tata Consultancy Services", sector: "IT" },
  { ticker: "INFY.NS", name: "Infosys", sector: "IT" },
];

describe("WatchlistManager", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.listTickers).mockResolvedValue(UNIVERSE);
  });

  it("excludes tickers already in the watchlist from the add options", async () => {
    vi.mocked(api.listWatchlistItems).mockResolvedValue([
      { ticker: "RELIANCE.NS", name: "Reliance Industries", sector: "Energy/Materials" },
    ]);

    render(<WatchlistManager watchlistId="wl-1" />);

    await waitFor(() => expect(screen.getByText(/RELIANCE/)).toBeInTheDocument());

    const select = screen.getByLabelText("Add a ticker to your watchlist");
    const options = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
    expect(options.some((o) => o?.includes("RELIANCE"))).toBe(false);
    expect(options.some((o) => o?.includes("TCS"))).toBe(true);
    expect(options.some((o) => o?.includes("INFY"))).toBe(true);
  });

  it("selecting a ticker and clicking Add calls the add endpoint", async () => {
    vi.mocked(api.listWatchlistItems).mockResolvedValue([]);
    vi.mocked(api.addWatchlistItem).mockResolvedValue(undefined);

    render(<WatchlistManager watchlistId="wl-1" />);
    await waitFor(() => expect(screen.getByLabelText("Add a ticker to your watchlist")).toBeInTheDocument());

    const select = screen.getByLabelText("Add a ticker to your watchlist") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "TCS.NS" } });
    fireEvent.click(screen.getByText("Add"));

    await waitFor(() => expect(api.addWatchlistItem).toHaveBeenCalledWith("wl-1", "TCS.NS"));
  });

  it("clicking Remove on a listed ticker calls the remove endpoint", async () => {
    vi.mocked(api.listWatchlistItems).mockResolvedValue([
      { ticker: "RELIANCE.NS", name: "Reliance Industries", sector: "Energy/Materials" },
    ]);
    vi.mocked(api.removeWatchlistItem).mockResolvedValue(undefined);

    render(<WatchlistManager watchlistId="wl-1" />);
    await waitFor(() => expect(screen.getByText(/RELIANCE/)).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Remove RELIANCE.NS"));

    await waitFor(() => expect(api.removeWatchlistItem).toHaveBeenCalledWith("wl-1", "RELIANCE.NS"));
  });

  it("does not force a digest refetch itself — only calls its own list/add/remove endpoints", async () => {
    vi.mocked(api.listWatchlistItems).mockResolvedValue([]);
    vi.mocked(api.addWatchlistItem).mockResolvedValue(undefined);

    render(<WatchlistManager watchlistId="wl-1" />);
    await waitFor(() => expect(screen.getByLabelText("Add a ticker to your watchlist")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Add a ticker to your watchlist"), { target: { value: "TCS.NS" } });
    fireEvent.click(screen.getByText("Add"));

    await waitFor(() => expect(api.addWatchlistItem).toHaveBeenCalled());
    expect(api.fetchDigest).not.toHaveBeenCalled();
  });
});
