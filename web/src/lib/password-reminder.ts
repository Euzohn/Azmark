/**
 * Pure helpers for the password-age reminder banner. The server decides
 * WHETHER a reminder is due (UserRead.password_change_due, instance policy);
 * these only shape the message and the local 7-day snooze.
 */
export const PASSWORD_REMINDER_DISMISS_KEY = "azmark.password-reminder-dismissed";
export const PASSWORD_REMINDER_SNOOZE_DAYS = 7;

const DAY_MS = 86_400_000;

/** Whole days since the password was last changed; null when unknown/invalid. */
export function passwordAgeDays(
  changedAt: string | null | undefined,
  now: number,
): number | null {
  if (!changedAt) return null;
  const stamp = Date.parse(changedAt);
  if (Number.isNaN(stamp)) return null;
  return Math.max(0, Math.floor((now - stamp) / DAY_MS));
}

/** A dismissal hides the banner for 7 days; after that it may show again. */
export function isReminderSnoozed(dismissedAt: string | null, now: number): boolean {
  if (!dismissedAt) return false;
  const stamp = Date.parse(dismissedAt);
  if (Number.isNaN(stamp)) return false;
  return now - stamp < PASSWORD_REMINDER_SNOOZE_DAYS * DAY_MS;
}
