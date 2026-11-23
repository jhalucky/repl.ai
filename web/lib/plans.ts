export const ALERT_CHANNELS = ["email", "whatsapp", "telegram"] as const;
export type AlertChannel = (typeof ALERT_CHANNELS)[number];

export const PLAN_IDS = ["founder", "starter", "base", "super-active"] as const;
export type PlanId = (typeof PLAN_IDS)[number];

export const CHANNEL_LABELS: Record<AlertChannel, string> = {
  email: "Email",
  whatsapp: "WhatsApp",
  telegram: "Telegram",
};

export type Plan = {
  id: PlanId;
  name: string;
  tagline: string;
  monthlyUsd: number;
  yearlyUsd: number;
  recommended: boolean;
  listed: boolean;
  maxMailboxes: number;
  channels: readonly AlertChannel[];
  customSchedule: boolean;
  ctaLabel: string;
  highlights: readonly string[];
};

/**
 * Public grid is Starter / Base / Super Active. The owner plan is used on /register.
 */
export const plans: readonly Plan[] = [
  {
    id: "founder",
    name: "Manav",
    tagline: "The pipeline you already run. Always free for the founding team.",
    monthlyUsd: 0,
    yearlyUsd: 0,
    recommended: false,
    listed: false,
    maxMailboxes: 20,
    channels: ["email", "whatsapp", "telegram"],
    customSchedule: true,
    ctaLabel: "Continue as Manav",
    highlights: [
      "Current Gmail sync, classification, and digest",
      "Read-only Gmail access",
      "Daily email report",
      "No card, no trial clock",
    ],
  },
  {
    id: "starter",
    name: "Starter",
    tagline: "One inbox. One daily digest. Enough to stop missing replies.",
    monthlyUsd: 19,
    yearlyUsd: 190,
    recommended: false,
    listed: true,
    maxMailboxes: 1,
    channels: ["email"],
    customSchedule: true,
    ctaLabel: "Start with Starter",
    highlights: [
      "1 connected Gmail",
      "Email digest",
      "Needs-reply vs no-reply split",
      "Choose alert time and timezone",
    ],
  },
  {
    id: "base",
    name: "Base",
    tagline: "The default for people who live in more than one inbox.",
    monthlyUsd: 49,
    yearlyUsd: 490,
    recommended: true,
    listed: true,
    maxMailboxes: 5,
    channels: ["email", "whatsapp"],
    customSchedule: true,
    ctaLabel: "Choose Base",
    highlights: [
      "5 connected Gmail accounts",
      "Email and WhatsApp alerts",
      "Needs-reply vs no-reply split",
      "Choose alert time and timezone",
    ],
  },
  {
    id: "super-active",
    name: "Super Active",
    tagline: "Every mailbox, every channel, for high-volume operators.",
    monthlyUsd: 99,
    yearlyUsd: 990,
    recommended: false,
    listed: true,
    maxMailboxes: 15,
    channels: ["email", "whatsapp", "telegram"],
    customSchedule: true,
    ctaLabel: "Choose Super Active",
    highlights: [
      "15 connected Gmail accounts",
      "Email, WhatsApp, and Telegram",
      "Needs-reply vs no-reply split",
      "Choose alert time and timezone",
    ],
  },
] as const;

export const FOUNDER_PLAN_ID: PlanId = "founder";
export const RECOMMENDED_PLAN_ID: PlanId = "base";

export function getPlan(id: string): Plan | undefined {
  return plans.find((plan) => plan.id === id);
}

export function listedPlans(): Plan[] {
  return plans.filter((plan) => plan.listed);
}

export function founderPlan(): Plan {
  const plan = getPlan(FOUNDER_PLAN_ID);
  if (!plan) {
    throw new Error("Owner plan is missing from plans.ts");
  }
  return plan;
}

export function mailboxLimitLabel(plan: Plan): string {
  return plan.maxMailboxes === 1
    ? "1 mailbox"
    : `${plan.maxMailboxes} mailboxes`;
}

export function yearlySavingsUsd(plan: Plan): number {
  return Math.max(0, plan.monthlyUsd * 12 - plan.yearlyUsd);
}
