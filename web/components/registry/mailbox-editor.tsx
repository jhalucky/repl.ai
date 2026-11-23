"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { googleLoginHref, type ConnectedAccount } from "@/lib/api";
import { mailboxSchema, type MailboxForm } from "@/lib/founder-schema";
import { getPlan, type PlanId } from "@/lib/plans";

type Props = {
  planId: PlanId;
  alertEmail: string;
  accounts: ConnectedAccount[];
  next: string;
  justConnected?: string;
  showConnect?: boolean;
  requireAlertEmail?: boolean;
};

export function MailboxEditor({
  planId,
  alertEmail,
  accounts,
  next,
  justConnected,
  showConnect = false,
  requireAlertEmail = true,
}: Props) {
  const plan = getPlan(planId);
  const max = plan?.maxMailboxes ?? 1;
  const used = accounts.length;
  const atLimit = used >= max;
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<MailboxForm>({
    resolver: zodResolver(mailboxSchema),
    mode: "onChange",
    defaultValues: { email: "" },
  });

  function onAdd(values: MailboxForm) {
    const form = document.getElementById(`add-mailbox-${planId}`) as HTMLFormElement | null;
    const emailInput = form?.querySelector<HTMLInputElement>('input[name="email"]');
    if (emailInput) emailInput.value = values.email;
    form?.requestSubmit();
  }

  return (
    <section className="panel p-6" aria-labelledby="mailboxes-heading">
      <h2 id="mailboxes-heading" className="text-xl font-medium">
        Mailboxes
      </h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        {used} of {max} Gmail inboxes to track. Connect each one with Google
        (read-only).
      </p>

      {showConnect && !atLimit ? (
        <p className="mt-4">
          <a
            className="inline-flex min-h-11 items-center bg-[var(--fg)] px-5 text-sm font-medium text-[var(--bg)]"
            href={googleLoginHref(planId)}
          >
            Connect Gmail
          </a>
        </p>
      ) : null}

      {justConnected ? (
        <p
          role="status"
          className="mt-4 border border-[var(--ok)]/40 bg-[var(--ok)]/10 px-3 py-2 text-sm"
        >
          Connected {justConnected}
        </p>
      ) : null}

      {accounts.length === 0 ? (
        <p role="status" className="mt-4 text-sm text-[var(--muted)]">
          No mailboxes yet.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-[var(--line)] border-y border-[var(--line)]">
          {accounts.map((account) => (
            <li key={account.email} className="py-4">
              <p className="text-xs text-[var(--muted)]">
                {account.status}
                {account.last_synced_at ? ` · synced ${account.last_synced_at}` : ""}
              </p>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <form
                  action="/api/registry/mailboxes"
                  method="post"
                  className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row"
                >
                  <input type="hidden" name="action" value="replace" />
                  <input type="hidden" name="plan" value={planId} />
                  <input type="hidden" name="alert_email" value={alertEmail} />
                  <input type="hidden" name="old_email" value={account.email} />
                  <input type="hidden" name="next" value={next} />
                  <label className="sr-only" htmlFor={`edit-${account.email}`}>
                    Edit {account.email}
                  </label>
                  <input
                    id={`edit-${account.email}`}
                    name="new_email"
                    type="email"
                    required
                    defaultValue={account.email}
                    className="min-h-11 min-w-0 flex-1 border border-[var(--line)] bg-black/30 px-3 font-mono text-sm"
                  />
                  <button
                    type="submit"
                    className="min-h-11 border border-[var(--line)] px-4 text-sm hover:bg-white/10"
                  >
                    Save
                  </button>
                </form>
                <form action="/api/registry/mailboxes" method="post">
                  <input type="hidden" name="action" value="remove" />
                  <input type="hidden" name="plan" value={planId} />
                  <input type="hidden" name="alert_email" value={alertEmail} />
                  <input type="hidden" name="email" value={account.email} />
                  <input type="hidden" name="next" value={next} />
                  <button
                    type="submit"
                    className="min-h-11 border border-[var(--danger)]/50 px-4 text-sm text-[var(--danger)] hover:bg-[var(--danger)]/10"
                  >
                    Remove
                  </button>
                </form>
              </div>
            </li>
          ))}
        </ul>
      )}

      {requireAlertEmail && !alertEmail ? (
        <p role="status" className="mt-4 text-sm text-[var(--muted)]">
          Save an alert email first, then add mailboxes.
        </p>
      ) : atLimit ? (
        <p role="status" className="mt-4 text-sm text-[var(--danger)]">
          Mailbox limit reached. Remove one or upgrade to add more.
        </p>
      ) : (
        <>
          <form
            id={`add-mailbox-${planId}`}
            action="/api/registry/mailboxes"
            method="post"
            className="hidden"
          >
            <input type="hidden" name="action" value="add" />
            <input type="hidden" name="plan" value={planId} />
            <input type="hidden" name="alert_email" value={alertEmail} />
            <input type="hidden" name="next" value={next} />
            <input type="hidden" name="email" value="" />
          </form>
          <form className="mt-6 flex flex-col gap-3 sm:flex-row" onSubmit={handleSubmit(onAdd)}>
            <div className="min-h-[4.5rem] flex-1">
              <label htmlFor="mailbox-email" className="sr-only">
                Gmail address
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
              className="min-h-11 shrink-0 border border-[var(--line)] px-5 text-sm hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Add mailbox
            </button>
          </form>
        </>
      )}

    </section>
  );
}
