"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { notificationSchema, type NotificationForm } from "@/lib/founder-schema";
import { type PlanId } from "@/lib/plans";

type Props = {
  planId: PlanId;
  next: string;
  alertEmail: string;
  whatsapp: string;
  telegram: string;
  title?: string;
  description?: string;
  showMessaging?: boolean;
  submitLabel?: string;
};

export function ProfileForm({
  planId,
  next,
  alertEmail,
  whatsapp,
  telegram,
  title = "Your details",
  description = "Required once. This row is stored in the Excel sheet like any other user: alert email, WhatsApp, and Telegram.",
  showMessaging = true,
  submitLabel = "Save to sheet",
}: Props) {
  const formId = `profile-${planId}`;
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<NotificationForm>({
    resolver: zodResolver(notificationSchema),
    mode: "onChange",
    defaultValues: {
      email: alertEmail,
      whatsapp,
      telegram,
    },
  });

  function onValid(values: NotificationForm) {
    const form = document.getElementById(formId) as HTMLFormElement | null;
    if (!form) return;
    const set = (name: string, value: string) => {
      const input = form.querySelector<HTMLInputElement>(`input[name="${name}"]`);
      if (input) input.value = value;
    };
    set("alert_email", values.email);
    set("whatsapp", values.whatsapp);
    set("telegram", values.telegram);
    form.requestSubmit();
  }

  return (
    <section className="panel p-6" aria-labelledby={`${formId}-heading`}>
      <h2 id={`${formId}-heading`} className="text-xl font-medium">
        {title}
      </h2>
      <p className="mt-1 text-sm text-[var(--muted)]">{description}</p>

      <form id={formId} action="/api/registry" method="post" className="hidden">
        <input type="hidden" name="plan" value={planId} />
        <input type="hidden" name="next" value={next} />
        <input type="hidden" name="alert_email" />
        <input type="hidden" name="whatsapp" />
        <input type="hidden" name="telegram" />
      </form>

      <form className="mt-6 space-y-5" onSubmit={handleSubmit(onValid)}>
        <div className="min-h-[4.5rem]">
          <label htmlFor={`${formId}-email`} className="text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
            Alert email
          </label>
          <input
            id={`${formId}-email`}
            type="email"
            autoComplete="email"
            className="mt-2 min-h-11 w-full border border-[var(--line)] bg-black/30 px-3 text-sm"
            aria-invalid={errors.email ? true : undefined}
            {...register("email")}
          />
          <p className="mt-1 min-h-5 text-xs text-[var(--danger)]">
            {errors.email?.message ?? "\u00a0"}
          </p>
        </div>
        {showMessaging ? (
          <>
            <div className="min-h-[4.5rem]">
              <label htmlFor={`${formId}-whatsapp`} className="text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
                WhatsApp number
              </label>
              <input
                id={`${formId}-whatsapp`}
                type="tel"
                placeholder="+91…"
                className="mt-2 min-h-11 w-full border border-[var(--line)] bg-black/30 px-3 text-sm"
                aria-invalid={errors.whatsapp ? true : undefined}
                {...register("whatsapp")}
              />
              <p className="mt-1 min-h-5 text-xs text-[var(--danger)]">
                {errors.whatsapp?.message ?? "\u00a0"}
              </p>
            </div>
            <div className="min-h-[4.5rem]">
              <label htmlFor={`${formId}-telegram`} className="text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
                Telegram username or id
              </label>
              <input
                id={`${formId}-telegram`}
                type="text"
                placeholder="@username or 123456"
                className="mt-2 min-h-11 w-full border border-[var(--line)] bg-black/30 px-3 text-sm"
                aria-invalid={errors.telegram ? true : undefined}
                {...register("telegram")}
              />
              <p className="mt-1 min-h-5 text-xs text-[var(--danger)]">
                {errors.telegram?.message ?? "\u00a0"}
              </p>
            </div>
          </>
        ) : null}
        <button
          type="submit"
          disabled={!isValid}
          className="min-h-11 bg-[var(--fg)] px-5 text-sm font-medium text-[var(--bg)] disabled:cursor-not-allowed disabled:bg-[var(--muted)]"
        >
          {submitLabel}
        </button>
      </form>
    </section>
  );
}
