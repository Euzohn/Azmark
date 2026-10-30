/**
 * Run with `npm test` (Node's built-in test runner; no extra dependencies).
 *
 * The timezone picker searches 400+ IANA zones. These helpers keep name and
 * offset matching predictable, and the offset label is what the picker shows
 * next to every row.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  COMMON_TIMEZONES,
  TIMEZONES,
  filterTimezones,
  parseOffsetQuery,
  timezoneOffsetLabel,
} from "./timezones.ts";

test("parseOffsetQuery understands offset inputs only", () => {
  assert.equal(parseOffsetQuery("+8"), "+8");
  assert.equal(parseOffsetQuery("-5"), "-5");
  assert.equal(parseOffsetQuery("utc+8"), "+8");
  assert.equal(parseOffsetQuery("UTC8"), "+8");
  assert.equal(parseOffsetQuery("gmt-5"), "-5");
  assert.equal(parseOffsetQuery("utc+5:30"), "+5:30");
  assert.equal(parseOffsetQuery("+0530"), "+5:30");
  // A bare number is ambiguous, so it stays a name search.
  assert.equal(parseOffsetQuery("8"), null);
  assert.equal(parseOffsetQuery("shanghai"), null);
  assert.equal(parseOffsetQuery(""), null);
});

test("filterTimezones matches names case-insensitively", () => {
  assert.ok(filterTimezones("shang").includes("Asia/Shanghai"));
  assert.ok(filterTimezones("SHANGHAI").includes("Asia/Shanghai"));
  // "_" is searchable as a space, so this is the natural way to type it.
  assert.ok(filterTimezones("new york").includes("America/New_York"));
  assert.equal(filterTimezones("not-a-real-zone").length, 0);
});

test("filterTimezones matches UTC offsets", () => {
  const plus8 = filterTimezones("utc+8");
  assert.ok(plus8.includes("Asia/Shanghai"));
  assert.ok(!plus8.includes("Asia/Tokyo")); // +9
  // ICU may canonicalize Kolkata to its legacy name.
  const india = filterTimezones("+5:30");
  assert.ok(india.includes("Asia/Calcutta") || india.includes("Asia/Kolkata"));
});

test("timezoneOffsetLabel follows DST", () => {
  assert.equal(timezoneOffsetLabel("Asia/Shanghai", new Date("2026-01-01T00:00:00Z")), "UTC+8");
  assert.equal(
    timezoneOffsetLabel("America/New_York", new Date("2026-01-15T12:00:00Z")),
    "UTC-5",
  );
  assert.equal(
    timezoneOffsetLabel("America/New_York", new Date("2026-07-15T12:00:00Z")),
    "UTC-4",
  );
  assert.equal(timezoneOffsetLabel("UTC", new Date("2026-01-01T00:00:00Z")), "UTC+0");
  assert.equal(timezoneOffsetLabel("Not/A_Zone"), "");
});

test("common zones are selectable", () => {
  for (const zone of COMMON_TIMEZONES) {
    assert.ok(TIMEZONES.includes(zone), `${zone} missing from TIMEZONES`);
  }
});