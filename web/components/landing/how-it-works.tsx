const steps = [
  {
    n: "01",
    title: "Connect",
    body: "Add the Gmail IDs you want tracked — company, org, or personal.",
  },
  {
    n: "02",
    title: "We classify",
    body: "Inbound threads are scored. We never store message bodies. You only see who still needs a reply.",
  },
  {
    n: "03",
    title: "You get a digest",
    body: "One alert at the time you pick. Needs-reply on top. Everything else filed as no reply needed.",
  },
] as const;

export function HowItWorks() {
  return (
    <section
      id="how"
      aria-labelledby="how-heading"
      className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24"
    >
      <h2 id="how-heading" className="font-display text-3xl tracking-tight sm:text-4xl">
        How it works
      </h2>
      <p className="mt-3 max-w-xl text-[var(--muted)]">
        Three steps. No inbox to live in. No mail sent on your behalf.
      </p>
      <ol className="mt-10 grid gap-4 md:grid-cols-3">
        {steps.map((step) => (
          <li
            key={step.n}
            className="panel min-h-[13rem] p-6"
          >
            <p className="font-mono text-xs tracking-widest text-[var(--accent)]">{step.n}</p>
            <h3 className="mt-4 text-xl font-medium">{step.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">{step.body}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
