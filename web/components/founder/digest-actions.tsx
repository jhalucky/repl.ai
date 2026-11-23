type Props = {
  digestHour: number;
  timezone: string;
};

export function DigestActions({ digestHour, timezone }: Props) {
  const hour = String(digestHour).padStart(2, "0");
  return (
    <section className="panel p-6" aria-labelledby="digest-heading">
      <h2 id="digest-heading" className="text-xl font-medium">
        Digest
      </h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        Daily report at {hour}:00 {timezone}. Uses the live Gmail sync and classifier.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <form action="/api/digest/run" method="post">
          <input type="hidden" name="hours" value="1" />
          <button
            type="submit"
            className="min-h-11 border border-[var(--line)] px-5 text-sm hover:bg-white/10"
          >
            Test last hour
          </button>
        </form>
        <form action="/api/digest/run" method="post">
          <button
            type="submit"
            className="min-h-11 border border-[var(--line)] px-5 text-sm hover:bg-white/10"
          >
            Send full report
          </button>
        </form>
      </div>
    </section>
  );
}
