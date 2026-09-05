import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DigestBrief } from "../DigestBrief";

describe("DigestBrief", () => {
  it("renders the brief text under a small 'Today' label", () => {
    render(
      <DigestBrief
        brief="HDFCBANK is the one signal that stands out today, moving 2.8σ outside its normal range."
        flags={null}
        ackedCount={0}
      />
    );
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(
      screen.getByText("HDFCBANK is the one signal that stands out today, moving 2.8σ outside its normal range.")
    ).toBeInTheDocument();
  });

  it("renders nothing at all when brief is null (zero active signals) — no empty/awkward line", () => {
    const { container } = render(<DigestBrief brief={null} flags={null} ackedCount={0} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("never renders any AI/robot/sparkle framing", () => {
    render(
      <DigestBrief
        brief="Two unusual moves today, concentrated in Banking/Finance — HDFCBANK is the most statistically unusual."
        flags={null}
        ackedCount={0}
      />
    );
    const text = document.body.textContent ?? "";
    expect(text.toLowerCase()).not.toMatch(/\bai\b|generated|sparkle|robot/);
  });

  it("derives stock-specific/sector-wide counts from the real flags, and omits acknowledged at zero", () => {
    render(
      <DigestBrief
        brief="Two signals today."
        flags={[
          { sector_relative: "stock_specific" } as never,
          { sector_relative: "stock_specific" } as never,
          { sector_relative: "sector_wide" } as never,
        ]}
        ackedCount={0}
      />
    );
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("stock-specific")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("sector-wide")).toBeInTheDocument();
    expect(screen.queryByText(/acknowledged/)).not.toBeInTheDocument();
  });

  it("shows a real session-scoped acknowledged count when > 0, labeled 'this session'", () => {
    render(<DigestBrief brief="One signal today." flags={[]} ackedCount={3} />);
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("acknowledged this session")).toBeInTheDocument();
  });
});
