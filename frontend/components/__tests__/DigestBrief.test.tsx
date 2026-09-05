import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DigestBrief } from "../DigestBrief";

describe("DigestBrief", () => {
  it("renders the brief text under a small 'Today' label", () => {
    render(<DigestBrief brief="HDFCBANK is the one signal that stands out today, moving 2.8σ outside its normal range." />);
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(
      screen.getByText("HDFCBANK is the one signal that stands out today, moving 2.8σ outside its normal range.")
    ).toBeInTheDocument();
  });

  it("renders nothing at all when brief is null (zero active signals) — no empty/awkward line", () => {
    const { container } = render(<DigestBrief brief={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("never renders any AI/robot/sparkle framing", () => {
    render(<DigestBrief brief="Two unusual moves today, concentrated in Banking/Finance — HDFCBANK is the most statistically unusual." />);
    const text = document.body.textContent ?? "";
    expect(text.toLowerCase()).not.toMatch(/\bai\b|generated|sparkle|robot/);
  });
});
