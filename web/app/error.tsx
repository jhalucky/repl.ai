"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-[50svh] max-w-lg flex-col justify-center px-4 py-16">
      <h1 className="font-display text-3xl">Something went wrong</h1>
      <p className="mt-3 text-sm text-[var(--muted)]">
        {error.message || "The page failed to load."}
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-6 inline-flex min-h-11 items-center justify-center bg-[var(--fg)] px-5 text-sm font-medium text-[var(--bg)]"
      >
        Try again
      </button>
    </main>
  );
}
