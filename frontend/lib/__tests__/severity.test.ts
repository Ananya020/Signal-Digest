import { describe, expect, it } from "vitest";
import { directionFromFlag, FRESHNESS_CONFIG, resolveRowStyle, SEVERITY_META } from "../severity";

describe("severity metadata — non-color cues", () => {
  it("every severity level has a non-empty label AND a distinct icon", () => {
    const icons = new Set<string>();
    for (const meta of Object.values(SEVERITY_META)) {
      expect(meta.label.length).toBeGreaterThan(0);
      expect(meta.icon.length).toBeGreaterThan(0);
      icons.add(meta.icon);
    }
    expect(icons.size).toBe(Object.keys(SEVERITY_META).length);
  });

  it("severity icons are never the direction arrows (▲/▼) — the two cues never collide", () => {
    for (const meta of Object.values(SEVERITY_META)) {
      expect(meta.icon).not.toBe("▲");
      expect(meta.icon).not.toBe("▼");
    }
  });
});

describe("directionFromFlag", () => {
  it("positive z_score is 'up'", () => {
    expect(directionFromFlag({ z_score: 2.5 })).toBe("up");
  });
  it("negative z_score is 'down'", () => {
    expect(directionFromFlag({ z_score: -2.5 })).toBe("down");
  });
});

describe("resolveRowStyle — two independent channels", () => {
  it("severity changes intensity (background tier) but not the arrow/hue direction", () => {
    const notableUp = resolveRowStyle("notable", "up");
    const extremeUp = resolveRowStyle("extreme", "up");
    expect(notableUp.direction).toBe(extremeUp.direction);
    expect(notableUp.arrow).toBe(extremeUp.arrow);
    expect(notableUp.rowBgClass).not.toBe(extremeUp.rowBgClass); // intensity differs
  });

  it("direction changes hue but not the severity icon/label", () => {
    const extremeUp = resolveRowStyle("extreme", "up");
    const extremeDown = resolveRowStyle("extreme", "down");
    expect(extremeUp.icon).toBe(extremeDown.icon);
    expect(extremeUp.label).toBe(extremeDown.label);
    expect(extremeUp.rowBgClass).not.toBe(extremeDown.rowBgClass); // hue differs
    expect(extremeUp.arrow).not.toBe(extremeDown.arrow);
  });

  it("badge intensity has three genuinely distinct steps (wash/soft/strong) within one hue", () => {
    const notable = resolveRowStyle("notable", "up");
    const significant = resolveRowStyle("significant", "up");
    const extreme = resolveRowStyle("extreme", "up");
    const tiers = [notable.badgeBgClass, significant.badgeBgClass, extreme.badgeBgClass];
    expect(new Set(tiers).size).toBe(3);
  });

  it("row background caps at the soft tier — Extreme's full solid fill stays on the badge, not the whole row (legibility)", () => {
    const significant = resolveRowStyle("significant", "up");
    const extreme = resolveRowStyle("extreme", "up");
    expect(extreme.rowBgClass).toBe(significant.rowBgClass);
    expect(extreme.badgeBgClass).not.toBe(significant.badgeBgClass);
  });

  it("extreme's badge text inverts to white for contrast against its solid fill", () => {
    expect(resolveRowStyle("extreme", "up").badgeTextClass).toBe("text-white");
    expect(resolveRowStyle("notable", "up").badgeTextClass).not.toBe("text-white");
  });
});

describe("freshness config", () => {
  it("every freshness state has a non-empty label and icon", () => {
    for (const config of Object.values(FRESHNESS_CONFIG)) {
      expect(config.label.length).toBeGreaterThan(0);
      expect(config.icon.length).toBeGreaterThan(0);
    }
  });

  it("all five states are visually distinct (color), not just distinct by label text", () => {
    const colorClasses = Object.values(FRESHNESS_CONFIG).map((c) => c.textClass);
    expect(new Set(colorClasses).size).toBe(5);
  });
});
