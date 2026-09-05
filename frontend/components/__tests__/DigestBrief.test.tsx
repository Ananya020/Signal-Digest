import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DigestBrief } from "../DigestBrief";

describe("DigestBrief", () => {
  it("renders the brief text under a small 'Today' label", () => {
    render(
      <DigestBrief
        brief="HDFCBANK is the one signal that stands out today, moving 2.8σ outside its normal range."
        flags={null}
      />
    );
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(
      screen.getByText("HDFCBANK is the one signal that stands out today, moving 2.8σ outside its normal range.")
    ).toBeInTheDocument();
  });

  it("renders nothing at all when brief is null (zero active signals) — no empty/awkward line", () => {
    const { container } = render(<DigestBrief brief={null} flags={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("never renders any AI/robot/sparkle framing", () => {
    render(
      <DigestBrief
        brief="Two unusual moves today, concentrated in Banking/Finance — HDFCBANK is the most statistically unusual."
        flags={null}
      />
    );
    const text = document.body.textContent ?? "";
    expect(text.toLowerCase()).not.toMatch(/\bai\b|generated|sparkle|robot/);
  });

  it("derives stock-specific/sector-wide counts from the real flags, never invents an acknowledged count", () => {
    render(
      <DigestBrief
        brief="Two signals today."
        flags={[
          { sector_relative: "stock_specific" } as never,
          { sector_relative: "stock_specific" } as never,
          { sector_relative: "sector_wide" } as never,
        ]}
      />
    );
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("stock-specific")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("sector-wide")).toBeInTheDocument();
    expect(screen.queryByText("acknowledged")).not.toBeInTheDocument();
  });
});
