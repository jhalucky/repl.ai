const needsReply = [
  { from: "Priya · Acme", subject: "Can you confirm Friday’s slot?", wait: "4h" },
  { from: "Noah · Design", subject: "Feedback on the deck", wait: "1d" },
];

const noReply = [
  { from: "GitHub", subject: "A deploy finished on main", wait: "—" },
  { from: "Calendar", subject: "Accepted: standup", wait: "—" },
];

function Column({
  title,
  tone,
  rows,
}: {
  title: string;
  tone: "need" | "skip";
  rows: typeof needsReply;
}) {
  const accent = tone === "need" ? "text-[var(--danger)]" : "text-[var(--ok)]";
  return (
    <div className="min-h-[16rem] border border-[var(--line)] bg-[var(--bg-elevated)] p-4">
      <p className={`text-xs font-medium uppercase tracking-[0.16em] ${accent}`}>{title}</p>
      <ul className="mt-4 space-y-3">
        {rows.map((row) => (
          <li
            key={row.subject}
            className="border border-[var(--line)] bg-black/20 px-3 py-3"
          >
            <p className="text-sm font-medium">{row.subject}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {row.from}
              {row.wait !== "—" ? ` · waiting ${row.wait}` : ""}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AlertPreview() {
  return (
    <section
      aria-labelledby="preview-heading"
      className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12"
    >
      <div className="panel p-6 sm:p-8">
        <h2 id="preview-heading" className="font-display text-3xl tracking-tight sm:text-4xl">
          A sample alert
        </h2>
        <p className="mt-3 max-w-xl text-[var(--muted)]">
          Every digest splits the same way: act on these, ignore the rest.
        </p>
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <Column title="Needs your reply" tone="need" rows={needsReply} />
          <Column title="No reply needed" tone="skip" rows={noReply} />
        </div>
      </div>
    </section>
  );
}
