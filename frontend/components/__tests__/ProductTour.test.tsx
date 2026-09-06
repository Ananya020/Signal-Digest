import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductTour } from "../ProductTour";

const noop = () => {};

describe("ProductTour", () => {
  // The one property worth testing explicitly: this overlay must never
  // appear unless a user explicitly clicked "Take a tour" (see AppHeader).
  // No first-visit/localStorage auto-launch logic exists anywhere in this
  // component, and this test pins that down across every prop combination.
  it("never renders when open is false, under any demoMode value", () => {
    const { rerender } = render(<ProductTour open={false} onClose={noop} demoMode={false} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText(/of \d+/)).not.toBeInTheDocument();

    rerender(<ProductTour open={false} onClose={noop} demoMode={true} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText(/of \d+/)).not.toBeInTheDocument();
  });

  it("renders nothing on mount even without any explicit open prop transition (default closed)", () => {
    render(<ProductTour open={false} onClose={noop} demoMode={false} />);
    expect(document.body.textContent).not.toMatch(/Freshness indicator|Today's Brief|Unusualness score/);
  });

  it("starts at step 1 of 5 when opened without demo_mode, and Next advances through steps", () => {
    render(<ProductTour open={true} onClose={noop} demoMode={false} />);
    expect(screen.getByText("1 of 5")).toBeInTheDocument();
    expect(screen.getByText("Freshness indicator")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("2 of 5")).toBeInTheDocument();
    expect(screen.getByText("Today's Brief")).toBeInTheDocument();
  });

  it("Back navigates to the previous step and is disabled on step 1", () => {
    render(<ProductTour open={true} onClose={noop} demoMode={false} />);
    expect(screen.getByText("Back")).toBeDisabled();

    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("Back")).not.toBeDisabled();
    fireEvent.click(screen.getByText("Back"));
    expect(screen.getByText("1 of 5")).toBeInTheDocument();
  });

  it("Skip exits the tour immediately regardless of step", () => {
    const onClose = vi.fn();
    render(<ProductTour open={true} onClose={onClose} demoMode={false} />);
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Skip"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("clicking Next on the final step (Done) exits the tour", () => {
    const onClose = vi.fn();
    render(<ProductTour open={true} onClose={onClose} demoMode={false} />);
    // 5 steps without demo mode: click through to the last one.
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("5 of 5")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Done"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("pressing Escape exits the tour at any step", () => {
    const onClose = vi.fn();
    render(<ProductTour open={true} onClose={onClose} demoMode={false} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("includes the demo-controls step, mirroring the same demo_mode gate DemoControls itself uses, only when demoMode is true", () => {
    render(<ProductTour open={true} onClose={noop} demoMode={true} />);
    expect(screen.getByText("1 of 6")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("6 of 6")).toBeInTheDocument();
    expect(screen.getByText("Demo controls")).toBeInTheDocument();
  });

  it("excludes the demo-controls step entirely when demoMode is false", () => {
    render(<ProductTour open={true} onClose={noop} demoMode={false} />);
    expect(screen.getByText("1 of 5")).toBeInTheDocument();
    expect(screen.queryByText("Demo controls")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    // Step 5 of 5 is "Watchlist", not "Demo controls" — confirms the step
    // was skipped rather than just relabeled.
    expect(screen.getByText("5 of 5")).toBeInTheDocument();
    expect(screen.getByText("Watchlist")).toBeInTheDocument();
    expect(screen.queryByText("Demo controls")).not.toBeInTheDocument();
  });

  it("re-opening the tour always restarts at step 1, never resumes or persists dismissal", () => {
    const { rerender } = render(<ProductTour open={true} onClose={noop} demoMode={false} />);
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("3 of 5")).toBeInTheDocument();

    rerender(<ProductTour open={false} onClose={noop} demoMode={false} />);
    rerender(<ProductTour open={true} onClose={noop} demoMode={false} />);
    expect(screen.getByText("1 of 5")).toBeInTheDocument();
  });
});
