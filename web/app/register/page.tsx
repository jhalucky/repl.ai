import { MailboxEditor } from "@/components/registry/mailbox-editor";
import { ProfileForm } from "@/components/registry/profile-form";
import { fetchRegistry } from "@/lib/api";
import { DEFAULT_OWNER_NAME, inboxSetupTitle } from "@/lib/brand";
import { PLAN_IDS, getPlan, type PlanId } from "@/lib/plans";

export const dynamic = "force-dynamic";

function isPlanId(value: string | undefined): value is PlanId {
  return Boolean(value && (PLAN_IDS as readonly string[]).includes(value));
}

export default async function RegisterPage({
  searchParams,
}: {
  searchParams: Promise<{
    plan?: string;
    alert_email?: string;
    name?: string;
    connected?: string;
    notice?: string;
    error?: string;
  }>;
}) {
  const params = await searchParams;
  const planId: PlanId = isPlanId(params.plan) ? params.plan : "founder";
  const plan = getPlan(planId);
  const ownerName =
    params.name?.trim() || (planId === "founder" ? DEFAULT_OWNER_NAME : "");
  const heading = ownerName ? inboxSetupTitle(ownerName) : "Register your inboxes";
  const isOwnerSetup = planId === "founder";
  const lookup = params.alert_email?.trim() || "";
  let loadError: string | null = null;
  let registry = {
    alert_email: lookup,
    whatsapp: "",
    telegram: "",
    complete: false,
    accounts: [] as Awaited<ReturnType<typeof fetchRegistry>>["accounts"],
  };

  try {
    const payload = await fetchRegistry(planId, lookup || undefined);
    registry = {
      alert_email: payload.alert_email || lookup,
      whatsapp: payload.whatsapp,
      telegram: payload.telegram,
      complete: Boolean(payload.complete && payload.alert_email),
      accounts: payload.accounts,
    };
  } catch (error) {
    loadError = error instanceof Error ? error.message : "Could not load registry";
  }

  const next = "/register";
  const alertEmail = registry.alert_email || lookup;
  const hasMailbox = registry.accounts.length > 0;
  const showAlert = isOwnerSetup ? hasMailbox : true;

  return (
    <div className="site-shell">
      <header className="border-b border-[var(--line)] bg-[var(--bg)]">
        <div className="mx-auto flex min-h-16 max-w-3xl items-center justify-between gap-4 px-4 sm:px-6">
          <p className="font-display text-lg tracking-tight">Repl.ai</p>
          <p className="text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
            {ownerName || plan?.name || "Register"}
          </p>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
        <h1 className="font-display text-4xl tracking-tight">{heading}</h1>
        <p className="mt-3 max-w-xl text-[var(--muted)]">
          {isOwnerSetup
            ? "Connect the Gmail inboxes to watch, then where alerts should go."
            : "Add the Gmail IDs to track and where alerts should go."}
        </p>

        {params.notice ? (
          <p role="status" className="mt-6 border border-[var(--ok)]/40 bg-[var(--ok)]/10 px-3 py-2 text-sm">
            {params.notice}
          </p>
        ) : null}
        {params.error ? (
          <p role="alert" className="mt-6 border border-[var(--danger)]/40 bg-[var(--danger)]/10 px-3 py-2 text-sm">
            {params.error}
          </p>
        ) : null}
        {loadError ? (
          <p role="alert" className="mt-6 border border-[var(--danger)]/40 bg-[var(--danger)]/10 px-3 py-2 text-sm">
            {loadError}. Is the API running on port 8001?
          </p>
        ) : null}

        {!isOwnerSetup ? (
          <form className="panel mt-8 p-6" method="get">
            <input type="hidden" name="plan" value={planId} />
            {ownerName ? <input type="hidden" name="name" value={ownerName} /> : null}
            <label htmlFor="lookup-email" className="text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
              Your alert email
            </label>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <input
                id="lookup-email"
                name="alert_email"
                type="email"
                required
                defaultValue={lookup}
                placeholder="you@company.com"
                className="min-h-11 flex-1 border border-[var(--line)] bg-black/30 px-3 text-sm"
              />
              <button type="submit" className="min-h-11 border border-[var(--line)] px-4 text-sm hover:bg-white/10">
                Load
              </button>
            </div>
          </form>
        ) : null}

        <div className="mt-8 space-y-4">
          <MailboxEditor
            planId={planId}
            alertEmail={alertEmail}
            accounts={registry.accounts}
            next={next}
            justConnected={params.connected}
            showConnect={isOwnerSetup}
            requireAlertEmail={false}
          />
          {showAlert ? (
            <ProfileForm
              planId={planId}
              next={next}
              alertEmail={alertEmail}
              whatsapp={isOwnerSetup ? "" : registry.whatsapp}
              telegram={isOwnerSetup ? "" : registry.telegram}
              title="Where to receive alerts"
              description="Daily digest of threads that still need a reply. One address."
              showMessaging={!isOwnerSetup}
              submitLabel="Save alert email"
            />
          ) : (
            <p role="status" className="panel p-6 text-sm text-[var(--muted)]">
              Connect a Gmail inbox first. Then we will ask where to send the digest.
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
