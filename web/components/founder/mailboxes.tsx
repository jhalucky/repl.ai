"use client";

import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { googleLoginHref, type ConnectedAccount } from "@/lib/api";
import { FOUNDER_PLAN_ID, founderPlan } from "@/lib/plans";
import { mailboxSchema, type MailboxForm } from "@/lib/founder-schema";

type Props = {
  accounts: ConnectedAccount[];
  justConnected?: string;
};

export function Mailboxes({ accounts, justConnected }: Props) {
  const plan = founderPlan();
  const used = accounts.length;
  const atLimit = used >= plan.maxMailboxes;
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<MailboxForm>({
    resolver: zodResolver(mailboxSchema),
    mode: "onChange",
    defaultValues: { email: "" },
  });

  const empty = accounts.length === 0;

  const connectHref = useMemo(() => googleLoginHref(FOUNDER_PLAN_ID), []);

  function onSubmit(values: MailboxForm) {
    const url = new URL(connectHref);
    url.searchParams.set("login_hint", values.email);
    window.location.assign(url.toString());
  }

  return (
    <section className="panel p-6" aria-labelledby="mailboxes-heading">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="mailboxes-heading" className="text-xl font-medium">
            Mailboxes
          </h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {used} of {plan.maxMailboxes} used. Connect each Gmail with Google
            (read-only).
          </p>
        </div>
      </div>

      {justConnected ? (
        <p role="status" className="mt-4 border border-[var(--ok)]/40 bg-[var(--ok)]/10 px-3 py-2 text-sm">
          Connected {justConnected}
        </p>
      ) : null}

      {empty ? (
        <p role="status" className="mt-4 text-sm text-[var(--muted)]">
          No Gmail accounts connected yet.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-[var(--line)] border-y border-[var(--line)]">
          {accounts.map((account) => (
            <li key={account.email} className="flex min-h-14 items-center justify-between gap-3 py-3">
              <div>
                <p className="font-mono text-sm">{account.email}</p>
                <p className="text-xs text-[var(--muted)]">
                  {account.status}
                  {account.last_synced_at ? ` · synced ${account.last_synced_at}` : " · not synced yet"}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {atLimit ? (
        <p role="status" className="mt-4 text-sm text-[var(--danger)]">
          Mailbox limit reached for this inbox setup.
        </p>
      ) : (
        <form className="mt-6 flex flex-col gap-3 sm:flex-row" onSubmit={handleSubmit(onSubmit)}>
          <div className="min-h-[4.5rem] flex-1">
            <label htmlFor="mailbox-email" className="sr-only">
              Gmail address to connect
            </label>
            <input
              id="mailbox-email"
              type="email"
              autoComplete="email"
              placeholder="name@gmail.com"
              className="min-h-11 w-full border border-[var(--line)] bg-black/30 px-3 text-sm"
              aria-invalid={errors.email ? true : undefined}
              {...register("email")}
            />
            <p className="mt-1 min-h-5 text-xs text-[var(--danger)]">
              {errors.email?.message ?? "\u00a0"}
            </p>
          </div>
          <button
            type="submit"
            disabled={!isValid || atLimit}
            className="min-h-11 shrink-0 bg-[var(--fg)] px-5 text-sm font-medium text-[var(--bg)] disabled:cursor-not-allowed disabled:bg-[var(--muted)]"
          >
            Connect Gmail
          </button>
        </form>
      )}
    </section>
  );
}
