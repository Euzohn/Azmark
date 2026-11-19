/**
 * Soft-keyboard inset for the AI page's fixed mobile composer.
 *
 * On iOS Safari (and Chrome with `interactive-widget=resizes-visual`) the
 * soft keyboard shrinks only the *visual* viewport: `window.innerHeight`
 * (the layout viewport) stays put, so a `position: fixed` composer pinned
 * above the bottom nav ends up hidden behind the keyboard. The overlap
 * between the two viewports' bottoms is exactly the obscured height:
 *
 *     overlap = innerHeight - visualViewport.height - visualViewport.offsetTop
 *
 * Browsers that resize the layout viewport instead (classic Android
 * behaviour) keep the overlap at ~0 — the fixed composer already rides
 * above the keyboard there, so no adjustment is needed.
 *
 * Kept pure so the arithmetic is pinned by the Node test runner, following
 * the ai-deeplink / ai-history pattern.
 */

/**
 * Overlaps smaller than this are browser chrome, not a keyboard: URL-bar
 * show/hide animations briefly desynchronise the two viewports by a few
 * dozen pixels. Phone keyboards cover 200px+, so 80px stays clear of chrome
 * noise while still catching compact keyboards.
 */
export const KEYBOARD_OVERLAP_THRESHOLD = 80;

/** Height (px) of the layout viewport's bottom strip that the visual
 * viewport cannot see — the soft keyboard, when one is open. Clamped at 0
 * and rounded because the viewport APIs report fractional pixels. */
export function visualViewportOverlap(
  innerHeight: number,
  viewportHeight: number,
  viewportOffsetTop: number,
): number {
  return Math.max(0, Math.round(innerHeight - viewportHeight - viewportOffsetTop));
}

/**
 * Bottom inset (px) to lift the fixed composer above the soft keyboard.
 * `0` means "keep the CSS default" (sitting above the bottom nav). Desktop
 * keeps the composer in normal flow, so it never adjusts. Pinch-zoom also
 * shrinks the visual viewport (scale > 1) but is not a keyboard — while
 * zoomed, the overlap reflects the zoom, so no adjustment is made.
 */
export function composerKeyboardInset(
  innerHeight: number,
  viewportHeight: number,
  viewportOffsetTop: number,
  isDesktop: boolean,
  scale = 1,
): number {
  // 1.01 tolerates floating-point noise around scale === 1.
  if (isDesktop || scale > 1.01) return 0;
  const overlap = visualViewportOverlap(innerHeight, viewportHeight, viewportOffsetTop);
  return overlap >= KEYBOARD_OVERLAP_THRESHOLD ? overlap : 0;
}