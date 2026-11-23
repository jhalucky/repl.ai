const items = [
  {
    q: "What do you store?",
    a: "Thread metadata only: subject, sender, timestamps, and our classification. Message bodies are never persisted or logged. Refresh tokens are encrypted at rest.",
  },
  {
    q: "Is Gmail access read-only?",
    a: "Yes. We request gmail.readonly. Repl.ai cannot send, delete, archive, or modify mail. Alerts go out over a separate channel you choose, not through Gmail send.",
  },
  {
    q: "How do I delete my data?",
    a: "From settings you can request deletion of connected accounts, classifications, and tokens. Until that page ships, email support and we remove the row and encrypted tokens.",
  },
] as const;

export function Faq() {
  return (
    <section
      id="faq"
      aria-labelledby="faq-heading"
      className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-24"
    >
      <h2 id="faq-heading" className="font-display text-3xl tracking-tight sm:text-4xl">
        FAQ
      </h2>
      <div className="mt-8 divide-y divide-[var(--line)] border-y border-[var(--line)]">
        {items.map((item) => (
          <details key={item.q} className="group py-4">
            <summary className="cursor-pointer list-none text-base font-medium marker:content-none [&::-webkit-details-marker]:hidden">
              <span className="flex items-center justify-between gap-4">
                {item.q}
                <span aria-hidden className="text-[var(--muted)] group-open:hidden">
                  +
                </span>
                <span aria-hidden className="hidden text-[var(--muted)] group-open:inline">
                  −
                </span>
              </span>
            </summary>
            <p className="mt-3 text-sm leading-relaxed text-[var(--muted)]">{item.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
