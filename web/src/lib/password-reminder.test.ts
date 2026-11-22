/**
 * Run with `npm test` (Node's built-in test runner; no extra dependencies).
 *
 * The server decides whether the reminder is due; these helpers only shape
 * the message (whole days, defensive against bad timestamps) and the local
 * 7-day snooze window.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  PASSWORD_REMINDER_SNOOZE_DAYS,
  isReminderSnoozed,
  passwordAgeDays,
} from "./password-reminder.ts";

const NOW = Date.parse("2026-11-21T12:00:00Z");
const DAY_MS = 86_400_000;

test("passwordAgeDays counts whole days and clamps clock skew", () => {
  assert.equal(passwordAgeDays("2026-11-21T12:00:00Z", NOW), 0);
  assert.equal(passwordAgeDays("2026-11-11T12:00:00Z", NOW), 10);
  // One hour short of ten full days is still nine.
  assert.equal(passwordAgeDays("2026-11-11T13:00:00Z", NOW), 9);
  // A future timestamp (client clock behind the server) never goes negative.
  assert.equal(passwordAgeDays("2026-12-01T00:00:00Z", NOW), 0);
  assert.equal(passwordAgeDays(null, NOW), null);
  assert.equal(passwordAgeDays(undefined, NOW), null);
  assert.equal(passwordAgeDays("not-a-date", NOW), null);
});

test("isReminderSnoozed hides for 7 days then resurfaces", () => {
  assert.equal(isReminderSnoozed(null, NOW), false);
  assert.equal(isReminderSnoozed("garbage", NOW), false);
  const recent = new Date(NOW - (PASSWORD_REMINDER_SNOOZE_DAYS * DAY_MS - 1000)).toISOString();
  assert.equal(isReminderSnoozed(recent, NOW), true);
  const expired = new Date(NOW - PASSWORD_REMINDER_SNOOZE_DAYS * DAY_MS).toISOString();
  assert.equal(isReminderSnoozed(expired, NOW), false);
});
