/**
 * Run with `npm test` (Node's built-in test runner; no extra dependencies).
 *
 * The status sweep reports X-Status-Updated on every parallel query of a page
 * load; the toast must aggregate those reports into ONE notice instead of a
 * stack, and ignore zero/invalid totals.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { notifyStatusUpdate, resetStatusToast, useStatusToast } from "./status-toast.ts";

test("notifyStatusUpdate aggregates parallel reports into one toast", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  resetStatusToast();

  notifyStatusUpdate(2);
  notifyStatusUpdate(3);
  // Still inside the aggregation window: nothing shown yet.
  assert.equal(useStatusToast.getState().count, null);

  t.mock.timers.tick(600);
  assert.equal(useStatusToast.getState().count, 5);

  // A later batch of changes shows a fresh toast.
  notifyStatusUpdate(1);
  t.mock.timers.tick(600);
  assert.equal(useStatusToast.getState().count, 1);

  resetStatusToast();
  assert.equal(useStatusToast.getState().count, null);
});

test("notifyStatusUpdate ignores zero and invalid counts", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  resetStatusToast();

  notifyStatusUpdate(0);
  notifyStatusUpdate(-2);
  notifyStatusUpdate(Number.NaN);
  notifyStatusUpdate(Number.POSITIVE_INFINITY);
  t.mock.timers.tick(1000);
  assert.equal(useStatusToast.getState().count, null);

  resetStatusToast();
});
