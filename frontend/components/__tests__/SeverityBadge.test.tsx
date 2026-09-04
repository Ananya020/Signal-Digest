import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeverityBadge } from "../SeverityBadge";

describe("SeverityBadge", () => {
  it("renders text label and icon together for 'notable' (never color alone)", () => {
    render(<SeverityBadge severity="notable" direction="up" />);
    expect(screen.getByText("Notable")).toBeInTheDocument();
    expect(screen.getByText("●")).toBeInTheDocument();
  });

  it("renders distinct text+icon for each severity level, independent of direction", () => {
    const { rerender } = render(<SeverityBadge severity="notable" direction="up" />);
    expect(screen.getByText("Notable")).toBeInTheDocument();

    rerender(<SeverityBadge severity="significant" direction="down" />);
    expect(screen.getByText("Significant")).toBeInTheDocument();
    expect(screen.getByText("◆")).toBeInTheDocument();

    rerender(<SeverityBadge severity="extreme" direction="up" />);
    expect(screen.getByText("Extreme")).toBeInTheDocument();
    expect(screen.getByText("■")).toBeInTheDocument();
  });

  it("severity icon stays the same regardless of direction — icon is the severity cue, not the direction cue", () => {
    const { rerender } = render(<SeverityBadge severity="extreme" direction="up" />);
    expect(screen.getByText("■")).toBeInTheDocument();

    rerender(<SeverityBadge severity="extreme" direction="down" />);
    expect(screen.getByText("■")).toBeInTheDocument();
  });
});
