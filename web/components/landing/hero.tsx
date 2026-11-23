import { ButtonLink } from "@/components/ui/button-link";
import { PRODUCT_NAME } from "@/lib/brand";
import { RECOMMENDED_PLAN_ID, getPlan } from "@/lib/plans";

export function Hero() {
  const recommended = getPlan(RECOMMENDED_PLAN_ID);

  return (
    <section
      id="top"
      aria-labelledby="hero-heading"
      className="mx-auto grid min-h-[min(100svh,44rem)] max-w-6xl content-center px-4 py-16 sm:px-6 sm:py-24"
    >
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--accent-2)]">
        {PRODUCT_NAME} · Gmail reply tracker
      </p>
      <h1
        id="hero-heading"
        className="font-display mt-4 max-w-3xl text-4xl leading-[1.1] tracking-tight sm:text-6xl"
      >
        The emails that still need you, once a day.
      </h1>
      <p className="mt-5 max-w-xl text-base leading-relaxed text-[var(--muted)] sm:text-lg">
        Connect every Gmail you actually use. We classify inbound threads. You
        get one digest — needs a reply, or it doesn&apos;t.
      </p>
      <div className="mt-8 flex min-h-12 flex-wrap items-center gap-3">
        {recommended ? (
          <ButtonLink href={`/register?plan=${recommended.id}`}>
            {recommended.ctaLabel}
          </ButtonLink>
        ) : null}
        <ButtonLink href="#how" variant="ghost">
          See how it works
        </ButtonLink>
      </div>
    </section>
  );
}
