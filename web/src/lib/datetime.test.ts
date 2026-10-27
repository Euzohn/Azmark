/**
 * Run with `npm test` (Node's built-in test runner; no extra dependencies).
 *
 * These helpers guard the "time & statistics consistency" contract: a record
 * is always rendered in its own location's timezone — never silently in the
 * viewer's browser zone — and legacy/invalid zones degrade to UTC.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  daysUntilDeparture,
  displayTimezone,
  formatZonedDateTime,
  fromZonedInput,
  toZonedInput,
  zonedDateKey,
} from "./datetime.ts";

test("displayTimezone keeps valid zones and falls back to UTC", () => {
  assert.equal(displayTimezone("Asia/Shanghai"), "Asia/Shanghai");
  assert.equal(displayTimezone(null), "UTC");
  assert.equal(displayTimezone(""), "UTC");
  assert.equal(displayTimezone("Not/A_Zone"), "UTC");
});

test("zonedDateKey groups by the location's calendar date", () => {
  // 23:30Z on Jan 31 is already Feb 1 in Hong Kong.
  assert.equal(zonedDateKey("2026-01-31T23:30:00Z", "Asia/Hong_Kong"), "2026-02-01");
  assert.equal(zonedDateKey("2026-01-31T23:30:00Z", "America/New_York"), "2026-01-31");
  // Missing zone must not depend on the host machine: default is UTC.
  assert.equal(zonedDateKey("2026-01-31T23:30:00Z", null), "2026-01-31");
  assert.equal(zonedDateKey(null, "Asia/Hong_Kong"), "unknown");
  assert.equal(zonedDateKey("garbage", "Asia/Hong_Kong"), "unknown");
});

test("zonedDateKey respects DST on the travel date", () => {
  // New York is UTC-5 in winter, UTC-4 in summer.
  assert.equal(zonedDateKey("2026-01-01T04:30:00Z", "America/New_York"), "2025-12-31");
  assert.equal(zonedDateKey("2026-07-01T03:30:00Z", "America/New_York"), "2026-06-30");
});

test("formatZonedDateTime renders in the record's zone with a zone label", () => {
  const text = formatZonedDateTime("2026-09-26T01:45:00Z", "en-US", "Asia/Hong_Kong");
  assert.match(text, /09\/26\/2026/);
  assert.match(text, /09:45/);
  assert.match(text, /GMT\+8|HKT/);
  assert.equal(formatZonedDateTime(null, "en-US", "Asia/Hong_Kong"), "—");
  assert.equal(formatZonedDateTime("garbage", "en-US", "Asia/Hong_Kong"), "—");
});

test("formatZonedDateTime treats an invalid zone as UTC instead of throwing", () => {
  const text = formatZonedDateTime("2026-09-26T01:45:00Z", "en-US", "Not/A_Zone");
  assert.match(text, /01:45/);
});

test("daysUntilDeparture counts calendar days at the departure location", () => {
  const now = new Date("2026-09-24T20:00:00Z"); // Sep 25 in Hong Kong
  assert.equal(daysUntilDeparture("2026-09-26T01:45:00Z", "Asia/Hong_Kong", now), 1);
  assert.equal(daysUntilDeparture("2026-09-25T23:00:00Z", "Asia/Hong_Kong", now), 1);
  assert.equal(daysUntilDeparture("2026-09-25T01:00:00Z", "Asia/Hong_Kong", now), 0);
  assert.equal(daysUntilDeparture("2026-09-20T01:00:00Z", "Asia/Hong_Kong", now), -5);
  assert.equal(daysUntilDeparture(null, "Asia/Hong_Kong", now), null);
});

test("form round-trip preserves the instant across zones and unambiguous DST edges", () => {
  for (const [instant, tz] of [
    ["2026-09-26T01:45:00.000Z", "Asia/Hong_Kong"],
    ["2026-03-08T07:30:00.000Z", "America/New_York"], // spring-forward day
  ] as const) {
    const wall = toZonedInput(instant, tz);
    assert.equal(fromZonedInput(wall, tz), instant);
  }
});

test("ambiguous fall-back wall times consistently choose the earlier instant", () => {
  // datetime-local cannot encode which 01:30 occurred after clocks turn back.
  // We must be deterministic rather than accidentally depending on the host zone.
  assert.equal(
    fromZonedInput("2026-11-01T01:30", "America/New_York"),
    "2026-11-01T05:30:00.000Z",
  );
});
