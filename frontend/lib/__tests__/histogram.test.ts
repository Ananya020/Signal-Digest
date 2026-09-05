import { describe, expect, it } from "vitest";
import { buildHistogram, nearestBinCenter } from "../histogram";

describe("buildHistogram", () => {
  it("returns an empty array for no data", () => {
    expect(buildHistogram([])).toEqual([]);
  });

  it("buckets every point into exactly one bin — counts sum to the input length", () => {
    const returns = [-2, -1, -0.5, 0, 0.2, 0.5, 1, 1.5, 2, 3];
    const bins = buildHistogram(returns, 5);
    expect(bins).toHaveLength(5);
    expect(bins.reduce((sum, b) => sum + b.count, 0)).toBe(returns.length);
  });

  it("places a tight cluster of identical values into a single bin", () => {
    const bins = buildHistogram([1, 1, 1, 1], 4);
    const nonEmpty = bins.filter((b) => b.count > 0);
    expect(nonEmpty).toHaveLength(1);
    expect(nonEmpty[0].count).toBe(4);
  });
});

describe("nearestBinCenter", () => {
  it("picks the bin center closest to the target value", () => {
    const bins = [{ center: -1, count: 2 }, { center: 0, count: 5 }, { center: 1, count: 3 }];
    expect(nearestBinCenter(bins, 0.9)).toBe(1);
    expect(nearestBinCenter(bins, -0.1)).toBe(0);
  });
});
