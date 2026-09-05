import { describe, expect, it } from "vitest";
import { applyDigestPollResult, EMPTY_DIGEST_POLL_STATE, newFlagIds } from "../digestPoll";
import type { DigestResponse, Flag } from "../types";

function makeFlag(id: number): Flag {
  return {
    id,
    ticker: "RELIANCE.NS",
    trading_day: "2026-01-01",
    signal_type: "price_zscore",
    z_score: 2.5,
    severity: "notable",
    severity_rank: 1,
    volume_ratio: 1.5,
    sector_relative: null,
    computed_at: "2026-01-01T00:00:00Z",
    provider_state_at_computation: "replay_simulated",
    since_last_ack: null,
  };
}

function digest(flags: Flag[]): DigestResponse {
  return { freshness: "LIVE", detail: "mode=normal", flags, brief: null, events: [] };
}

describe("applyDigestPollResult", () => {
  it("a 304 (notModified) leaves state exactly unchanged", () => {
    const prev = { data: digest([makeFlag(1)]), etag: "abc" };
    const next = applyDigestPollResult(prev, { notModified: true });
    expect(next).toBe(prev); // same reference — never overwritten
  });

  it("a 200 updates data and etag", () => {
    const prev = EMPTY_DIGEST_POLL_STATE;
    const result = { notModified: false as const, data: digest([makeFlag(1)]), etag: '"newhash"' };
    const next = applyDigestPollResult(prev, result);
    expect(next.data).toBe(result.data);
    expect(next.etag).toBe('"newhash"');
  });

  it("a 200 with a null etag header keeps the previous etag rather than clearing it", () => {
    const prev = { data: digest([]), etag: '"oldhash"' };
    const result = { notModified: false as const, data: digest([makeFlag(1)]), etag: null };
    const next = applyDigestPollResult(prev, result);
    expect(next.etag).toBe('"oldhash"');
  });
});

describe("newFlagIds", () => {
  it("returns ids present in next but not prev", () => {
    const prev = { data: digest([makeFlag(1)]), etag: "a" };
    const next = { data: digest([makeFlag(1), makeFlag(2)]), etag: "b" };
    expect(newFlagIds(prev, next)).toEqual([2]);
  });

  it("returns empty when nothing new", () => {
    const prev = { data: digest([makeFlag(1)]), etag: "a" };
    const next = { data: digest([makeFlag(1)]), etag: "a" };
    expect(newFlagIds(prev, next)).toEqual([]);
  });

  it("returns empty when next has no data yet", () => {
    expect(newFlagIds(EMPTY_DIGEST_POLL_STATE, EMPTY_DIGEST_POLL_STATE)).toEqual([]);
  });
});
