/**
 * Run with `npm test` (Node's built-in test runner; no extra dependencies).
 *
 * The currency picker must offer real ISO 4217 codes so typos like "RMB"
 * (which is not a currency code) cannot be saved. These tests pin the shape
 * of the curated list and the runtime-derived full list.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { allCurrencyCodes, COMMON_CURRENCIES } from "./currencies.ts";

test("common currencies are well-formed, unique ISO codes", () => {
  assert.equal(new Set(COMMON_CURRENCIES).size, COMMON_CURRENCIES.length);
  for (const code of COMMON_CURRENCIES) {
    assert.match(code, /^[A-Z]{3}$/);
  }
  // The traveller-facing essentials must be present, CNY first.
  for (const code of ["CNY", "USD", "EUR", "JPY", "HKD"]) {
    assert.ok(COMMON_CURRENCIES.includes(code as (typeof COMMON_CURRENCIES)[number]), code);
  }
  assert.equal(COMMON_CURRENCIES[0], "CNY");
});

test("allCurrencyCodes is a sorted, unique ISO 4217 list", () => {
  const codes = allCurrencyCodes();
  assert.ok(codes.includes("CNY"));
  assert.ok(codes.includes("USD"));
  assert.equal(new Set(codes).size, codes.length);

  const sorted = [...codes].sort((a, b) => a.localeCompare(b));
  assert.deepEqual(codes, sorted);
});

test("RMB is not a currency code (the picker prevents that typo)", () => {
  assert.equal(COMMON_CURRENCIES.includes("RMB" as never), false);
  assert.equal(allCurrencyCodes().includes("RMB"), false);
});
