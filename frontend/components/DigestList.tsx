"use client";

import type { Flag } from "@/lib/types";
import { DigestRow } from "./DigestRow";
import { SkeletonRows } from "./SkeletonRows";

export function DigestList({
  flags,
  error,
  pendingNewCount,
  onPullInNew,
  onAck,
  onSelect,
}: {
  flags: Flag[] | null;
  error: string | null;
  pendingNewCount: number;
  onPullInNew: () => void;
  onAck: (flagId: number) => void;
  onSelect: (flag: Flag) => void;
}) {
  if (error) {
    return (
      <div className="rounded-md bg-down-wash px-3 py-4 text-sm text-down-text">
        Couldn&apos;t load the digest: {error}
      </div>
    );
  }

  if (flags === null) {
    return <SkeletonRows />;
  }

  return (
    <div className="flex flex-col gap-3">
      {pendingNewCount > 0 && (
        <button
          onClick={onPullInNew}
          className="focus-ring flex w-full items-center justify-center rounded-md bg-cobalt-wash px-3 py-2 text-sm font-medium text-cobalt transition-colors hover:bg-cobalt/15"
        >
          Show {pendingNewCount} new signal{pendingNewCount > 1 ? "s" : ""}
        </button>
      )}

      {/* Anti-Container Architecture (design.md): edge-to-edge rows with
          hairline dividers, no nested bordered card wrapping the list. */}
      {flags.length === 0 ? (
        <div className="px-3 py-10 text-center text-sm text-ink-muted">Nothing unusual right now. All caught up.</div>
      ) : (
        <ul>
          {flags.map((flag) => (
            <DigestRow key={flag.id} flag={flag} onAck={onAck} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </div>
  );
}
