import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppHeader } from "../AppHeader";

const noop = () => {};

describe("AppHeader", () => {
  it("renders the signalDigest wordmark", () => {
    render(
      <AppHeader onAboutClick={noop} onAddStockClick={noop} onTourClick={noop} providerStatus={null} onFaultChanged={noop} />
    );
    expect(screen.getByText("signal")).toBeInTheDocument();
    expect(screen.getByText("Digest")).toBeInTheDocument();
  });

  it("renders PRODUCT.md's exact core-promise tagline, not invented copy", () => {
    render(
      <AppHeader onAboutClick={noop} onAddStockClick={noop} onTourClick={noop} providerStatus={null} onFaultChanged={noop} />
    );
    expect(
      screen.getByText("Know in five seconds what actually changed — not what always jitters — and why.")
    ).toBeInTheDocument();
  });

  it("clicking About calls the provided handler", () => {
    const onAboutClick = vi.fn();
    render(
      <AppHeader
        onAboutClick={onAboutClick}
        onAddStockClick={noop}
        onTourClick={noop}
        providerStatus={null}
        onFaultChanged={noop}
      />
    );
    fireEvent.click(screen.getByText("About"));
    expect(onAboutClick).toHaveBeenCalledOnce();
  });

  it("clicking Add stock calls the provided handler", () => {
    const onAddStockClick = vi.fn();
    render(
      <AppHeader
        onAboutClick={noop}
        onAddStockClick={onAddStockClick}
        onTourClick={noop}
        providerStatus={null}
        onFaultChanged={noop}
      />
    );
    fireEvent.click(screen.getByLabelText("Search or add a stock"));
    expect(onAddStockClick).toHaveBeenCalledOnce();
  });

  it("clicking Take a tour calls the provided handler", () => {
    const onTourClick = vi.fn();
    render(
      <AppHeader
        onAboutClick={noop}
        onAddStockClick={noop}
        onTourClick={onTourClick}
        providerStatus={null}
        onFaultChanged={noop}
      />
    );
    fireEvent.click(screen.getByText("Take a tour"));
    expect(onTourClick).toHaveBeenCalledOnce();
  });

  it("does not render demo controls when demo_mode is false or status is unknown", () => {
    render(
      <AppHeader onAboutClick={noop} onAddStockClick={noop} onTourClick={noop} providerStatus={null} onFaultChanged={noop} />
    );
    expect(screen.queryByLabelText("Demo controls")).not.toBeInTheDocument();

    render(
      <AppHeader
        onAboutClick={noop}
        onAddStockClick={noop}
        onTourClick={noop}
        providerStatus={{ state: "LIVE", last_successful_fetch: "", age_seconds: 1, detail: "", demo_mode: false }}
        onFaultChanged={noop}
      />
    );
    expect(screen.queryByLabelText("Demo controls")).not.toBeInTheDocument();
  });

  it("renders demo controls when the real status says demo_mode is true", () => {
    render(
      <AppHeader
        onAboutClick={noop}
        onAddStockClick={noop}
        onTourClick={noop}
        providerStatus={{ state: "LIVE", last_successful_fetch: "", age_seconds: 1, detail: "", demo_mode: true }}
        onFaultChanged={noop}
      />
    );
    expect(screen.getByLabelText("Demo controls")).toBeInTheDocument();
  });
});
