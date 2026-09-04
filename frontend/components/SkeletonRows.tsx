export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <ul className="animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i} className="flex items-start justify-between gap-3 border-b border-zinc-100 px-3 py-3 last:border-0 dark:border-zinc-800">
          <div className="flex flex-1 flex-col gap-2">
            <div className="flex items-center gap-2">
              <div className="h-4 w-20 rounded bg-zinc-200 dark:bg-zinc-800" />
              <div className="h-5 w-16 rounded-full bg-zinc-200 dark:bg-zinc-800" />
            </div>
            <div className="h-3 w-3/4 rounded bg-zinc-200 dark:bg-zinc-800" />
            <div className="h-3 w-24 rounded bg-zinc-200 dark:bg-zinc-800" />
          </div>
          <div className="h-6 w-14 rounded-full bg-zinc-200 dark:bg-zinc-800" />
        </li>
      ))}
    </ul>
  );
}
