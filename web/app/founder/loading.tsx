export default function FounderLoading() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-14" role="status" aria-live="polite">
      <span className="sr-only">Loading inbox setup</span>
      <div className="h-10 w-64 animate-pulse bg-white/10" />
      <div className="mt-6 h-40 animate-pulse bg-white/10" />
      <div className="mt-4 h-40 animate-pulse bg-white/10" />
    </div>
  );
}
