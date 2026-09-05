import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DirectionArrow, SeverityBadge } from "../SeverityBadge";

describe("SeverityBadge", () => {
  it("renders text label and icon together for 'notable' (never color alone)", () => {
    const { container } = render(<SeverityBadge severity="notable" />);
    expect(screen.getByText("Notable")).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders a distinct label for each severity level", () => {
    const { rerender } = render(<SeverityBadge severity="notable" />);
    expect(screen.getByText("Notable")).toBeInTheDocument();

    rerender(<SeverityBadge severity="significant" />);
    expect(screen.getByText("Significant")).toBeInTheDocument();

    rerender(<SeverityBadge severity="extreme" />);
    expect(screen.getByText("Extreme")).toBeInTheDocument();
  });

  it("does not take a direction prop — severity's color/icon is independent of price direction", () => {
    // @ts-expect-error direction is intentionally not part of this component's props anymore
    render(<SeverityBadge severity="extreme" direction="down" />);
    expect(screen.getByText("Extreme")).toBeInTheDocument();
  });
});

describe("DirectionArrow", () => {
  it("renders an icon for 'up'", () => {
    const { container } = render(<DirectionArrow direction="up" />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders a visually distinct icon for 'down'", () => {
    const up = render(<DirectionArrow direction="up" />);
    const upSvg = up.container.querySelector("svg")?.outerHTML;

    const down = render(<DirectionArrow direction="down" />);
    const downSvg = down.container.querySelector("svg")?.outerHTML;

    expect(upSvg).not.toEqual(downSvg);
  });
});
