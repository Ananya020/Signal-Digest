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
      <div className="rounded-md border border-red-200 bg-red-50 px-3 py-4 text-sm text-red-700">
        Couldn&apos;t load the digest: {error}
      </div>
    );
  }

  if (flags === null) {
    return <SkeletonRows />;
  }

  return (
    <div className="flex flex-col gap-2">
      {pendingNewCount > 0 && (
        <button
          onClick={onPullInNew}
          className="self-center rounded-full bg-blue-600 px-3 py-1 text-xs font-medium text-white shadow hover:bg-blue-700"
        >
          {pendingNewCount} new update{pendingNewCount > 1 ? "s" : ""} — click to view
        </button>
      )}

      {flags.length === 0 ? (
        <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900">
          Nothing unusual right now — every flagged move has been acknowledged.
        </div>
      ) : (
        <ul className="rounded-md border border-zinc-200 dark:border-zinc-800">
          {flags.map((flag) => (
            <DigestRow key={flag.id} flag={flag} onAck={onAck} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </div>
  );
}
