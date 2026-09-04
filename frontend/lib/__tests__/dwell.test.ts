import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ACK_DWELL_MS, scheduleDwellAck } from "../dwell";

describe("scheduleDwellAck", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("does not fire before the dwell delay elapses", () => {
    const callback = vi.fn();
    scheduleDwellAck(ACK_DWELL_MS, callback);

    vi.advanceTimersByTime(ACK_DWELL_MS - 1);
    expect(callback).not.toHaveBeenCalled();
  });

  it("fires once the dwell delay has elapsed", () => {
    const callback = vi.fn();
    scheduleDwellAck(ACK_DWELL_MS, callback);

    vi.advanceTimersByTime(ACK_DWELL_MS);
    expect(callback).toHaveBeenCalledOnce();
  });

  it("cancel prevents the callback from firing at all", () => {
    const callback = vi.fn();
    const cancel = scheduleDwellAck(ACK_DWELL_MS, callback);
    cancel();

    vi.advanceTimersByTime(ACK_DWELL_MS * 2);
    expect(callback).not.toHaveBeenCalled();
  });
});
