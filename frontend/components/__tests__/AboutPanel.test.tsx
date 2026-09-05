import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AboutPanel } from "../AboutPanel";

describe("AboutPanel", () => {
  it("renders as an accessible, labeled dialog", () => {
    render(<AboutPanel onClose={() => {}} />);
    const dialog = screen.getByRole("dialog", { name: "About this build" });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("mentions the two Groww engineering posts cited in PRODUCT.md", () => {
    render(<AboutPanel onClose={() => {}} />);
    expect(screen.getByText(/Improving the Efficiency of Rendering User Holdings/)).toBeInTheDocument();
    expect(screen.getByText(/Holding Revamp Went Live/)).toBeInTheDocument();
  });

  it("does not claim investment advice or live market data", () => {
    render(<AboutPanel onClose={() => {}} />);
    expect(screen.getByText(/does not provide investment advice/)).toBeInTheDocument();
    expect(screen.getByText(/not a live market feed/)).toBeInTheDocument();
  });

  it("clicking the close button calls onClose", () => {
    const onClose = vi.fn();
    render(<AboutPanel onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("clicking the backdrop calls onClose, but clicking inside the panel does not", () => {
    const onClose = vi.fn();
    render(<AboutPanel onClose={onClose} />);
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();

    // The backdrop is the dialog's parent element.
    fireEvent.click(screen.getByRole("dialog").parentElement!);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("pressing Escape calls onClose", () => {
    const onClose = vi.fn();
    render(<AboutPanel onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
