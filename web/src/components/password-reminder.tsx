"use client";

import { KeyRound, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";
import {
  PASSWORD_REMINDER_DISMISS_KEY,
  isReminderSnoozed,
  passwordAgeDays,
} from "@/lib/password-reminder";

/**
 * Non-blocking password-age reminder. The server decides WHETHER to remind
 * (password_change_due follows the admin-configured threshold); this banner
 * only renders it and lets the user snooze it for 7 days. Mounted inside the
 * app shell's main column — the shell gates on auth hydration, so the
 * localStorage read never runs during SSR.
 */
export function PasswordReminder() {
  const { t } = useI18n();
  const user = useAuth((s) => s.user);
  // Freeze "now" at mount: render must stay pure, and a banner does not need
  // to tick across midnight.
  const [now] = useState(() => Date.now());
  // Per-account snooze: switching users in the same browser must not inherit
  // the previous account's dismissal.
  const dismissKey = user ? `${PASSWORD_REMINDER_DISMISS_KEY}:${user.id}` : PASSWORD_REMINDER_DISMISS_KEY;
  const [snoozed, setSnoozed] = useState(
    () =>
      typeof window !== "undefined" &&
      isReminderSnoozed(window.localStorage.getItem(dismissKey), now),
  );

  if (!user?.password_change_due || snoozed) return null;

  const days = passwordAgeDays(user.password_changed_at, now);
  const dismiss = () => {
    window.localStorage.setItem(dismissKey, new Date().toISOString());
    setSnoozed(true);
  };

  return (
    <div
      role="status"
      className="mb-5 flex items-start gap-3 rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm animate-fade-in-up"
    >
      <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
      <p className="flex-1">
        {days !== null ? t("passwordReminder.text", { days }) : t("passwordReminder.textGeneric")}
      </p>
      <Link
        href="/settings"
        className="shrink-0 font-medium text-warning underline-offset-2 hover:underline"
      >
        {t("passwordReminder.action")}
      </Link>
      <button
        type="button"
        onClick={dismiss}
        aria-label={t("passwordReminder.dismiss")}
        className="shrink-0 rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
