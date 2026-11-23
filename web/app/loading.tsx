export default function Loading() {
  return (
    <div className="site-shell mx-auto max-w-6xl px-4 py-24 sm:px-6" role="status" aria-live="polite">
      <span className="sr-only">Loading</span>
      <div className="h-4 w-32 animate-pulse rounded bg-white/10" />
      <div className="mt-6 h-16 w-full max-w-2xl animate-pulse rounded bg-white/10" />
      <div className="mt-4 h-8 w-full max-w-xl animate-pulse rounded bg-white/10" />
    </div>
  );
}
