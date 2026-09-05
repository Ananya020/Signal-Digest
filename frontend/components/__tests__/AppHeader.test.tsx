import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppHeader } from "../AppHeader";

describe("AppHeader", () => {
  it("renders the signalDigest wordmark", () => {
    render(<AppHeader onAboutClick={() => {}} />);
    expect(screen.getByText("signal")).toBeInTheDocument();
    expect(screen.getByText("Digest")).toBeInTheDocument();
  });

  it("renders PRODUCT.md's exact core-promise tagline, not invented copy", () => {
    render(<AppHeader onAboutClick={() => {}} />);
    expect(
      screen.getByText("Know in five seconds what actually changed — not what always jitters — and why.")
    ).toBeInTheDocument();
  });

  it("clicking About calls the provided handler", () => {
    const onAboutClick = vi.fn();
    render(<AppHeader onAboutClick={onAboutClick} />);
    fireEvent.click(screen.getByText("About"));
    expect(onAboutClick).toHaveBeenCalledOnce();
  });
});
