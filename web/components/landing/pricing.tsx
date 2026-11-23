"use client";

import { useMemo, useState } from "react";
import { ButtonLink } from "@/components/ui/button-link";
import {
  CHANNEL_LABELS,
  type Plan,
  listedPlans,
  yearlySavingsUsd,
} from "@/lib/plans";

type Interval = "monthly" | "yearly";

function priceLabel(plan: Plan, interval: Interval): string {
  if (interval === "yearly") return `$${plan.yearlyUsd}`;
  return `$${plan.monthlyUsd}`;
}

function cadence(interval: Interval): string {
  return interval === "yearly" ? "/year" : "/month";
}

function PlanCard({ plan, interval }: { plan: Plan; interval: Interval }) {
  const savings = yearlySavingsUsd(plan);
  return (
    <article
      className={[
        "panel flex min-h-[28rem] flex-col p-6",
        plan.recommended ? "border-[var(--accent)] bg-[var(--accent)]/10" : "",
      ].join(" ")}
    >
      <div className="min-h-7">
        {plan.recommended ? (
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--accent)]">
            Recommended
          </p>
        ) : (
          <p className="text-xs tracking-[0.16em] text-transparent">Plan</p>
        )}
      </div>
      <h3 className="mt-2 text-2xl font-medium">{plan.name}</h3>
      <p className="mt-2 min-h-[3rem] text-sm text-[var(--muted)]">{plan.tagline}</p>
      <p className="mt-6 font-display text-4xl tabular-nums">
        {priceLabel(plan, interval)}
        <span className="ml-1 align-middle text-base text-[var(--muted)]">
          {cadence(interval)}
        </span>
      </p>
      <p className="mt-1 min-h-5 text-xs text-[var(--muted)]">
        {interval === "yearly" && savings > 0 ? `Save $${savings} vs monthly` : "\u00a0"}
      </p>
      <ul className="mt-6 min-h-[8.5rem] space-y-2 text-sm text-[var(--muted)]">
        {plan.highlights.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <div className="mt-auto pt-6">
        <p className="text-sm text-[var(--muted)]">
          {plan.channels.length === 0
            ? "No alert channels on this plan."
            : `Alerts: ${plan.channels.map((channel) => CHANNEL_LABELS[channel]).join(", ")}`}
        </p>
        <ButtonLink
          href={`/register?plan=${plan.id}`}
          variant={plan.recommended ? "primary" : "ghost"}
          className="mt-4 w-full"
        >
          {plan.ctaLabel}
        </ButtonLink>
      </div>
    </article>
  );
}

export function Pricing() {
  const [interval, setInterval] = useState<Interval>("monthly");
  const publicPlans = useMemo(() => listedPlans(), []);

  return (
    <section
      id="pricing"
      aria-labelledby="pricing-heading"
      className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24"
    >
      <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="pricing-heading" className="font-display text-3xl tracking-tight sm:text-4xl">
            Pricing
          </h2>
          <p className="mt-3 max-w-xl text-[var(--muted)]">
            Three plans. Base is the default for more than one inbox.
          </p>
        </div>
        <div
          role="group"
          aria-label="Billing interval"
          className="inline-flex min-h-11 border border-[var(--line)] bg-black/30 p-1"
        >
          {(["monthly", "yearly"] as const).map((value) => {
            const selected = interval === value;
            return (
              <button
                key={value}
                type="button"
                aria-pressed={selected}
                onClick={() => setInterval(value)}
                className={[
                  "min-h-9 px-4 text-sm capitalize",
                  selected ? "bg-[var(--fg)] text-[var(--bg)]" : "text-[var(--muted)]",
                ].join(" ")}
              >
                {value}
              </button>
            );
          })}
        </div>
      </div>

      {publicPlans.length === 0 ? (
        <p
          role="status"
          className="panel mt-10 px-4 py-10 text-center text-[var(--muted)]"
        >
          Plans are not configured. Add listed plans in{" "}
          <code className="text-[var(--fg)]">lib/plans.ts</code>.
        </p>
      ) : (
        <div className="mt-10 grid gap-4 lg:grid-cols-3">
          {publicPlans.map((plan) => (
            <PlanCard key={plan.id} plan={plan} interval={interval} />
          ))}
        </div>
      )}
    </section>
  );
}
