/**
 * Year-specific closing line for the Travel Wrapped report.
 *
 * The closing used to be one fixed sentence for every year. It is now a
 * curated pool (copy lives in the i18n dictionaries, zh-CN + en-US) picked
 * deterministically by the report year: the same year always shows the same
 * line — the report is revisited, shared and switched back and forth — while
 * adjacent years always differ. With 12 lines the rotation repeats after 12
 * years, which no reader will notice.
 *
 * This module holds keys only, never copy, and stays pure so the selection
 * semantics are pinned by the Node test runner (ai-deeplink pattern).
 */

export const WRAPPED_CLOSING_KEYS = [
  "wrapped.closing.0",
  "wrapped.closing.1",
  "wrapped.closing.2",
  "wrapped.closing.3",
  "wrapped.closing.4",
  "wrapped.closing.5",
  "wrapped.closing.6",
  "wrapped.closing.7",
  "wrapped.closing.8",
  "wrapped.closing.9",
  "wrapped.closing.10",
  "wrapped.closing.11",
] as const;

export type WrappedClosingKey = (typeof WRAPPED_CLOSING_KEYS)[number];

/** The closing-line i18n key for a report year. Stable per year; adjacent
 * years map to different keys. The double modulo keeps negative years (and
 * year 0) in range instead of indexing with a negative remainder. */
export function wrappedClosingKey(year: number): WrappedClosingKey {
  const n = WRAPPED_CLOSING_KEYS.length;
  return WRAPPED_CLOSING_KEYS[((year % n) + n) % n];
}