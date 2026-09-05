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

const noop = () => {};

function search(query: string) {
  fireEvent.change(screen.getByPlaceholderText("Add a stock — e.g. TITAN"), { target: { value: query } });
}

describe("WatchlistManager", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.listTickers).mockResolvedValue(UNIVERSE);
  });

  it("clicking View history on a listed ticker navigates to that ticker's history", async () => {
    vi.mocked(api.listWatchlistItems).mockResolvedValue([
      { ticker: "RELIANCE.NS", name: "Reliance Industries", sector: "Energy/Materials" },
    ]);
    const onViewHistory = vi.fn();

    render(<WatchlistManager watchlistId="wl-1" onViewHistory={onViewHistory} />);
    await waitFor(() => expect(screen.getByText(/RELIANCE/)).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("View signal history for RELIANCE.NS"));
    expect(onViewHistory).toHaveBeenCalledWith("RELIANCE.NS", "Reliance Industries");
  });

  it("excludes tickers already in the watchlist from search results", async () => {
    vi.mocked(api.listWatchlistItems).mockResolvedValue([
      { ticker: "RELIANCE.NS", name: "Reliance Industries", sector: "Energy/Materials" },
    ]);

    render(<WatchlistManager watchlistId="wl-1" onViewHistory={noop} />);
    await waitFor(() => expect(screen.getByText(/RELIANCE/)).toBeInTheDocument());

    // "reliance" matches RELIANCE's own name, yet it must never appear a
    // second time (in the search results) — it's already in the watchlist,
    // shown once, in the existing-items list below.
    search("reliance");
    expect(screen.getAllByText("RELIANCE")).toHaveLength(1);

    search("t");
    expect(screen.getByText("TCS")).toBeInTheDocument();

    search("infy");
    expect(screen.getByText("INFY")).toBeInTheDocument();
  });

  it("searching for a ticker and clicking Add calls the add endpoint", async () => {
    vi.mocked(api.listWatchlistItems).mockResolvedValue([]);
    vi.mocked(api.addWatchlistItem).mockResolvedValue(undefined);

    render(<WatchlistManager watchlistId="wl-1" onViewHistory={noop} />);
    await waitFor(() => expect(screen.getByPlaceholderText("Add a stock — e.g. TITAN")).toBeInTheDocument());

    search("TCS");
    fireEvent.click(screen.getByText("Add"));

    await waitFor(() => expect(api.addWatchlistItem).toHaveBeenCalledWith("wl-1", "TCS.NS"));
  });

  it("clicking Remove on a listed ticker calls the remove endpoint", async () => {
    vi.mocked(api.listWatchlistItems).mockResolvedValue([
      { ticker: "RELIANCE.NS", name: "Reliance Industries", sector: "Energy/Materials" },
    ]);
    vi.mocked(api.removeWatchlistItem).mockResolvedValue(undefined);

    render(<WatchlistManager watchlistId="wl-1" onViewHistory={noop} />);
    await waitFor(() => expect(screen.getByText(/RELIANCE/)).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Remove RELIANCE.NS from watchlist"));

    await waitFor(() => expect(api.removeWatchlistItem).toHaveBeenCalledWith("wl-1", "RELIANCE.NS"));
  });

  it("does not force a digest refetch itself — only calls its own list/add/remove endpoints", async () => {
    vi.mocked(api.listWatchlistItems).mockResolvedValue([]);
    vi.mocked(api.addWatchlistItem).mockResolvedValue(undefined);

    render(<WatchlistManager watchlistId="wl-1" onViewHistory={noop} />);
    await waitFor(() => expect(screen.getByPlaceholderText("Add a stock — e.g. TITAN")).toBeInTheDocument());

    search("TCS");
    fireEvent.click(screen.getByText("Add"));

    await waitFor(() => expect(api.addWatchlistItem).toHaveBeenCalled());
    expect(api.fetchDigest).not.toHaveBeenCalled();
  });
});
