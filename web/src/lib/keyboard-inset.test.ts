import assert from "node:assert/strict";
import test from "node:test";
import {
  composerKeyboardInset,
  KEYBOARD_OVERLAP_THRESHOLD,
  visualViewportOverlap,
} from "./keyboard-inset.ts";

test("open keyboard lifts the composer by the full overlap", () => {
  // 844px layout viewport, visual viewport shrunk to 500px by the keyboard.
  assert.equal(composerKeyboardInset(844, 500, 0, false), 344);
});

test("page scroll offset while the keyboard is open is accounted for", () => {
  // iOS scrolls the visual viewport within the layout viewport; offsetTop
  // must be subtracted so the inset still equals the keyboard height.
  assert.equal(composerKeyboardInset(844, 480, 20, false), 344);
});

test("closed keyboard keeps the CSS default (above the bottom nav)", () => {
  assert.equal(composerKeyboardInset(844, 844, 0, false), 0);
});

test("URL-bar chrome noise below the threshold is ignored", () => {
  // Transient desync during URL-bar animation — not a keyboard.
  assert.equal(composerKeyboardInset(844, 800, 0, false), 0);
  assert.equal(visualViewportOverlap(844, 800, 0), 44);
});

test("threshold boundary: at the threshold lifts, one pixel below does not", () => {
  const at = KEYBOARD_OVERLAP_THRESHOLD;
  assert.equal(composerKeyboardInset(844, 844 - at, 0, false), at);
  assert.equal(composerKeyboardInset(844, 844 - (at - 1), 0, false), 0);
});

test("desktop never adjusts (composer is in normal flow)", () => {
  assert.equal(composerKeyboardInset(844, 500, 0, true), 0);
});

test("pinch-zoom is not a keyboard: no adjustment while zoomed", () => {
  // Zoom shrinks the visual viewport too, but scale > 1 marks it as zoom.
  assert.equal(composerKeyboardInset(844, 500, 0, false, 2), 0);
  // Floating-point noise around scale 1 still counts as the keyboard.
  assert.equal(composerKeyboardInset(844, 500, 0, false, 1.005), 344);
});

test("overlap is clamped at zero and rounded", () => {
  // Visual viewport taller than the layout viewport (zoom-out) → no inset.
  assert.equal(visualViewportOverlap(844, 900, 0), 0);
  assert.equal(composerKeyboardInset(844, 900, 0, false), 0);
  // Fractional viewport pixels are rounded to whole CSS pixels.
  assert.equal(visualViewportOverlap(844, 500.4, 0.2), 343);
});