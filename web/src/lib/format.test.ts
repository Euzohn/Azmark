/**
 * Run with `npm test` (Node's built-in test runner; no extra dependencies).
 *
 * formatBytes backs the storage-quota UI (admin table, settings card). Pin the
 * base-1024 boundaries and the defensive handling of zero / invalid input so a
 * regression cannot silently mislabel a user's quota.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { formatBytes } from "./format.ts";

test("formatBytes uses base-1024 units with one decimal", () => {
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(1024), "1.0 KB");
  assert.equal(formatBytes(1536), "1.5 KB");
  assert.equal(formatBytes(1024 * 1024), "1.0 MB");
  assert.equal(formatBytes(1024 * 1024 * 1024), "1.0 GB");
  assert.equal(formatBytes(1024 * 1024 * 1024 * 1024), "1.0 TB");
});

test("formatBytes rounds sub-KB values and guards invalid input", () => {
  assert.equal(formatBytes(10.4), "10 B");
  assert.equal(formatBytes(-5), "0 B");
  assert.equal(formatBytes(Number.NaN), "0 B");
  assert.equal(formatBytes(Number.POSITIVE_INFINITY), "0 B");
});
