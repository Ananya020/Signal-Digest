import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import { HistoryPanel } from "../HistoryPanel";

vi.mock("@/lib/api");

describe("HistoryPanel", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders real returned historical records, reverse chronological as given by the API", async () => {
    vi.mocked(api.fetchTickerFlags).mockResolvedValue([
      { trading_day: "2026-09-04", signal_type: "price_zscore", z_score: -4.12, severity: "extreme" },
      { trading_day: "2026-09-01", signal_type: "price_zscore", z_score: -2.17, severity: "notable" },
    ]);

    render(<HistoryPanel ticker="INFY.NS" name="Infosys" onClose={() => {}} />);

    await waitFor(() => expect(screen.getByText("EXTREME")).toBeInTheDocument());
    expect(screen.getByText("NOTABLE")).toBeInTheDocument();
    expect(screen.getByText(/-4.12σ/)).toBeInTheDocument();
    expect(screen.getAllByText("Price anomaly")).toHaveLength(2);
    expect(screen.getByText(/INFY/)).toBeInTheDocument();
    expect(screen.getByText(/Infosys/)).toBeInTheDocument();
    expect(api.fetchTickerFlags).toHaveBeenCalledWith("INFY.NS");
  });

  it("shows an intentional empty state for a ticker with no recorded flags, not a broken-looking table", async () => {
    vi.mocked(api.fetchTickerFlags).mockResolvedValue([]);

    render(<HistoryPanel ticker="TCS.NS" onClose={() => {}} />);

    await waitFor(() =>
      expect(screen.getByText("Nothing unusual has been recorded for this ticker.")).toBeInTheDocument()
    );
  });

  it("shows an error state distinct from the empty state on a fetch failure", async () => {
    vi.mocked(api.fetchTickerFlags).mockRejectedValue(new Error("500 Internal Server Error"));

    render(<HistoryPanel ticker="TCS.NS" onClose={() => {}} />);

    await waitFor(() => expect(screen.getByText(/Couldn't load history/)).toBeInTheDocument());
  });

  it("renders as an accessible, labeled dialog", async () => {
    vi.mocked(api.fetchTickerFlags).mockResolvedValue([]);
    render(<HistoryPanel ticker="TCS.NS" onClose={() => {}} />);
    const dialog = screen.getByRole("dialog", { name: "Historical changes" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });
});
