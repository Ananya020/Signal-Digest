export function SkeletonRows({ count = 3 }: { count?: number }) {
  return (
    <div className="animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="space-y-3 bg-surface-raised px-4 py-5 sm:px-6">
          <div className="flex gap-6">
            <div className="h-8 w-20 rounded bg-surface-subtle" />
            <div className="h-8 flex-1 rounded bg-surface-subtle" />
          </div>
          <div className="h-4 w-2/3 rounded bg-surface-subtle" />
          <div className="h-4 w-1/3 rounded bg-surface-subtle" />
        </div>
      ))}
    </div>
  );
}
