import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Flag } from "@/lib/types";
import { DigestList } from "../DigestList";

function makeFlag(overrides: Partial<Flag>): Flag {
  return {
    id: 1,
    ticker: "RELIANCE.NS",
    trading_day: "2026-01-01",
    signal_type: "price_zscore",
    z_score: 2.5,
    severity: "notable",
    severity_rank: 1,
    volume_ratio: 1.5,
    sector_relative: "stock_specific",
    computed_at: "2026-01-01T00:00:00Z",
    provider_state_at_computation: "replay_simulated",
    since_last_ack: null,
    ...overrides,
  };
}

describe("DigestList — Step B event grouping", () => {
  it("renders a single-member sector as an ordinary row, not an event card", () => {
    const flags = [makeFlag({ id: 1, ticker: "A.NS", sector_relative: "sector_wide" })];
    render(
      <DigestList
        flags={flags}
        events={[]}
        error={null}
        pendingNewCount={0}
        onPullInNew={() => {}}
        onAck={() => {}}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText("Show evidence")).toBeInTheDocument();
    expect(screen.queryByText(/stocks moving together/)).not.toBeInTheDocument();
  });

  it("renders a 2+-member sector-wide cluster as a collapsed event card, expandable to reveal real rows", () => {
    const flags = [
      makeFlag({ id: 1, ticker: "A.NS", z_score: 2.4, sector_relative: "sector_wide" }),
      makeFlag({ id: 2, ticker: "B.NS", z_score: -3.9, sector_relative: "sector_wide" }),
    ];
    const events = [{ sector: "Energy", tickers: ["A.NS", "B.NS"], strongest_z_score: 3.9 }];

    render(
      <DigestList
        flags={flags}
        events={events}
        error={null}
        pendingNewCount={0}
        onPullInNew={() => {}}
        onAck={() => {}}
        onSelect={() => {}}
      />
    );

    expect(screen.getByText("Energy: 2 stocks moving together")).toBeInTheDocument();
    // Collapsed by default — member rows not yet in the DOM.
    expect(screen.queryAllByText("Show evidence")).toHaveLength(0);

    fireEvent.click(screen.getByText("Energy: 2 stocks moving together"));
    expect(screen.getAllByText("Show evidence")).toHaveLength(2);
  });

  it("acking a member row inside an expanded event calls onAck with only that flag's id", () => {
    vi.useFakeTimers();
    const flags = [
      makeFlag({ id: 1, ticker: "A.NS", z_score: 2.4, sector_relative: "sector_wide" }),
      makeFlag({ id: 2, ticker: "B.NS", z_score: -3.9, sector_relative: "sector_wide" }),
    ];
    const events = [{ sector: "Energy", tickers: ["A.NS", "B.NS"], strongest_z_score: 3.9 }];
    const onAck = vi.fn();

    render(
      <DigestList
        flags={flags}
        events={events}
        error={null}
        pendingNewCount={0}
        onPullInNew={() => {}}
        onAck={onAck}
        onSelect={() => {}}
      />
    );

    fireEvent.click(screen.getByText("Energy: 2 stocks moving together"));
    act(() => {
      vi.advanceTimersByTime(1600); // clear the ack dwell delay (ACK_DWELL_MS)
    });
    fireEvent.click(screen.getAllByText("Acknowledge")[0]);
    expect(onAck).toHaveBeenCalledTimes(1);
    expect(onAck).toHaveBeenCalledWith(1);
    vi.useRealTimers();
  });

  it("a stock-specific flag never renders inside an event card even if its sector also has a sector-wide event", () => {
    const flags = [
      makeFlag({ id: 1, ticker: "A.NS", z_score: 2.4, sector_relative: "sector_wide" }),
      makeFlag({ id: 2, ticker: "B.NS", z_score: -3.9, sector_relative: "sector_wide" }),
      makeFlag({ id: 3, ticker: "C.NS", z_score: 9.9, sector_relative: "stock_specific" }),
    ];
    const events = [{ sector: "Energy", tickers: ["A.NS", "B.NS"], strongest_z_score: 3.9 }];

    render(
      <DigestList
        flags={flags}
        events={events}
        error={null}
        pendingNewCount={0}
        onPullInNew={() => {}}
        onAck={() => {}}
        onSelect={() => {}}
      />
    );

    // C.NS renders as its own ordinary row alongside the event card.
    expect(screen.getByText("Show evidence")).toBeInTheDocument();
    expect(screen.getByText("Energy: 2 stocks moving together")).toBeInTheDocument();
  });
});
