"use client";

import { Input } from "@/components/ui/input";

type Props = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type">;

/**
 * Native date input with a 4-digit year.
 *
 * `max` is functional, not decorative: Blink derives the year segment's digit
 * count from the field's range. Without a max the year accepts 6 digits and
 * never auto-advances to the month after 4 digits, while month/day do advance —
 * which makes the field feel broken. Capping at 9999-12-31 makes the year a
 * 4-digit segment, so typing the year moves the caret to the month.
 */
export function DateInput(props: Props) {
  return <Input type="date" max="9999-12-31" {...props} />;
}

/** Same 4-digit-year fix for `datetime-local` (year + month + day + time). */
export function DateTimeLocalInput(props: Props) {
  return <Input type="datetime-local" max="9999-12-31T23:59" {...props} />;
}
