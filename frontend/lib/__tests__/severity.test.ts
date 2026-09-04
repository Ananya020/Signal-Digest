import { describe, expect, it } from "vitest";
import { FRESHNESS_CONFIG, SEVERITY_CONFIG } from "../severity";

describe("severity/freshness badge config", () => {
  it("every severity level has a non-empty label AND icon, never color alone", () => {
    for (const config of Object.values(SEVERITY_CONFIG)) {
      expect(config.label.length).toBeGreaterThan(0);
      expect(config.icon.length).toBeGreaterThan(0);
      expect(config.textClass.length).toBeGreaterThan(0);
    }
  });

  it("every freshness state has a non-empty label AND icon, never color alone", () => {
    for (const config of Object.values(FRESHNESS_CONFIG)) {
      expect(config.label.length).toBeGreaterThan(0);
      expect(config.icon.length).toBeGreaterThan(0);
      expect(config.textClass.length).toBeGreaterThan(0);
    }
  });

  it("severity icons are distinct per level (not relying on color to differentiate)", () => {
    const icons = Object.values(SEVERITY_CONFIG).map((c) => c.icon);
    expect(new Set(icons).size).toBe(icons.length);
  });

  it("freshness icons are distinct per state", () => {
    const icons = Object.values(FRESHNESS_CONFIG).map((c) => c.icon);
    expect(new Set(icons).size).toBe(icons.length);
  });
});
