import assert from "node:assert/strict";
import test from "node:test";
import { hotelYear, mapYears, photoYear, routeYear } from "./map-years.ts";

test("routeYear uses the departure timezone, not UTC", () => {
  // 2026-12-31 18:00 UTC is already 2027-01-01 02:00 in Shanghai.
  const instant = "2026-12-31T18:00:00Z";
  assert.equal(routeYear({ departure_time: instant, departure_timezone: "Asia/Shanghai" }), 2027);
  // Legacy records without a zone fall back to UTC (same as the backend).
  assert.equal(routeYear({ departure_time: instant, departure_timezone: null }), 2026);
});

test("routeYear is null without a usable departure time", () => {
  assert.equal(routeYear({ departure_time: null, departure_timezone: "Asia/Shanghai" }), null);
  assert.equal(routeYear({ departure_time: "not-a-date", departure_timezone: null }), null);
});

test("hotelYear reads the check-in date", () => {
  assert.equal(hotelYear({ check_in: "2026-04-29" }), 2026);
  assert.equal(hotelYear({ check_in: "" }), null);
});

test("photoYear follows the browser-local display", () => {
  // Mid-day mid-year: the local year is 2026 in every real-world zone.
  assert.equal(photoYear({ captured_at: "2026-06-15T12:00:00Z" }), 2026);
  assert.equal(photoYear({ captured_at: null }), null);
  assert.equal(photoYear({ captured_at: "not-a-date" }), null);
});

test("mapYears collects distinct years across layers, newest first", () => {
  const years = mapYears({
    items: [
      { departure_time: "2025-03-01T08:00:00Z", departure_timezone: null },
      { departure_time: "2026-12-31T18:00:00Z", departure_timezone: "Asia/Shanghai" },
      { departure_time: null, departure_timezone: null },
    ],
    hotels: [{ check_in: "2025-05-01" }],
    photos: [{ captured_at: "2024-08-10T12:00:00Z" }, { captured_at: null }],
  });
  // The Shanghai flight lands in 2027; 2025 appears twice (route + hotel)
  // and must be deduped. No record falls in 2026.
  assert.deepEqual(years, [2027, 2025, 2024]);
  assert.deepEqual(mapYears(undefined), []);
  assert.deepEqual(mapYears({}), []);
});