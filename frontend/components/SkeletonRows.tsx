export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <ul className="animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i} className="flex flex-col gap-2 border-b border-l-2 border-hairline border-l-transparent px-4 py-3 last:border-b-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-4 w-20 rounded bg-surface-subtle" />
              <div className="h-3 w-16 rounded bg-surface-subtle" />
            </div>
            <div className="h-3 w-10 rounded bg-surface-subtle" />
          </div>
          <div className="h-3 w-3/4 rounded bg-surface-subtle" />
          <div className="h-5 w-20 rounded bg-surface-subtle" />
        </li>
      ))}
    </ul>
  );
}
