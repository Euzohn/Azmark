import assert from "node:assert/strict";
import test from "node:test";
import { WRAPPED_CLOSING_KEYS, wrappedClosingKey } from "./wrapped-closing.ts";

test("same year always picks the same closing line", () => {
  for (const year of [2024, 2025, 2026, 2027]) {
    assert.equal(wrappedClosingKey(year), wrappedClosingKey(year));
  }
});

test("adjacent years never share a closing line", () => {
  for (let year = 1970; year < 2100; year++) {
    assert.notEqual(wrappedClosingKey(year), wrappedClosingKey(year + 1));
  }
});

test("rotation wraps after the pool size", () => {
  const n = WRAPPED_CLOSING_KEYS.length;
  assert.equal(wrappedClosingKey(2026), wrappedClosingKey(2026 + n));
  assert.equal(wrappedClosingKey(2026), wrappedClosingKey(2026 - n));
});

test("every year maps to a key inside the pool", () => {
  for (const year of [-1, 0, 1, 1970, 2026, 9999]) {
    assert.ok(WRAPPED_CLOSING_KEYS.includes(wrappedClosingKey(year)));
  }
});

test("the pool covers every index exactly once", () => {
  const picked = new Set(WRAPPED_CLOSING_KEYS.map((_, i) => wrappedClosingKey(i)));
  assert.equal(picked.size, WRAPPED_CLOSING_KEYS.length);
});