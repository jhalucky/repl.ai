import { z } from "zod";

export const mailboxSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter a Gmail address")
    .email("Enter a valid email")
    .refine((value) => value.toLowerCase().includes("@"), "Enter a Gmail address"),
});

export type MailboxForm = z.infer<typeof mailboxSchema>;

const e164 = /^\+[1-9]\d{7,14}$/;

export const notificationSchema = z
  .object({
    email: z.string().trim().email("Enter a valid alert email"),
    whatsapp: z.string().trim(),
    telegram: z.string().trim(),
  })
  .superRefine((value, ctx) => {
    if (value.whatsapp && !e164.test(value.whatsapp)) {
      ctx.addIssue({
        code: "custom",
        message: "Use international format, like +9198…",
        path: ["whatsapp"],
      });
    }
    if (value.telegram && value.telegram.replace(/^@/, "").length < 3) {
      ctx.addIssue({
        code: "custom",
        message: "Enter a Telegram username or numeric id",
        path: ["telegram"],
      });
    }
  });

export type NotificationForm = z.infer<typeof notificationSchema>;
