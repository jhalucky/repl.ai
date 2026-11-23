const DEFAULT_API_URL = "http://127.0.0.1:8001";

export function apiOrigin(): string {
  return process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || DEFAULT_API_URL;
}

/** Existing FastAPI route. Extra `plan` query is ignored by the current backend. */
export function googleLoginHref(planId: string): string {
  const url = new URL("/auth/google/start", `${apiOrigin()}/`);
  url.searchParams.set("plan", planId);
  return url.toString();
}

export type ConnectedAccount = {
  email: string;
  status: string;
  last_synced_at: string | null;
};

export type AccountsPayload = {
  founder_alert_email: string;
  digest_hour: number;
  timezone: string;
  accounts: ConnectedAccount[];
};

export async function fetchAccounts(): Promise<AccountsPayload> {
  const response = await fetch(`${apiOrigin()}/accounts`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load accounts (${response.status})`);
  }
  return (await response.json()) as AccountsPayload;
}

export type RegistryPayload = {
  id: string;
  plan: string;
  alert_email: string;
  whatsapp: string;
  telegram: string;
  timezone: string;
  alert_hour: number;
  max_mailboxes: number;
  accounts: ConnectedAccount[];
  founder_alert_email?: string;
  digest_hour?: number;
  complete?: boolean;
};

export async function fetchRegistry(
  plan: string,
  alertEmail?: string,
): Promise<RegistryPayload> {
  const url = new URL("/registry", `${apiOrigin()}/`);
  url.searchParams.set("plan", plan);
  if (alertEmail) url.searchParams.set("alert_email", alertEmail);
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load registry (${response.status})`);
  }
  return (await response.json()) as RegistryPayload;
}
