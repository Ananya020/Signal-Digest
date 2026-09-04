import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeverityBadge } from "../SeverityBadge";

describe("SeverityBadge", () => {
  it("renders text label and icon together for 'notable' (never color alone)", () => {
    render(<SeverityBadge severity="notable" />);
    expect(screen.getByText("Notable")).toBeInTheDocument();
    // The icon glyph is a sibling text node inside the same badge, not css-only.
    expect(screen.getByText("●")).toBeInTheDocument();
  });

  it("renders distinct text+icon for each severity level", () => {
    const { rerender } = render(<SeverityBadge severity="notable" />);
    expect(screen.getByText("Notable")).toBeInTheDocument();

    rerender(<SeverityBadge severity="significant" />);
    expect(screen.getByText("Significant")).toBeInTheDocument();
    expect(screen.getByText("▲")).toBeInTheDocument();

    rerender(<SeverityBadge severity="extreme" />);
    expect(screen.getByText("Extreme")).toBeInTheDocument();
    expect(screen.getByText("■")).toBeInTheDocument();
  });
});
