import type { RecordSort } from "./types";

export function parseRecordSort(value: string | null): RecordSort {
  return value === "oldest" || value === "departure" || value === "arrival" || value === "created" ? value : "newest";
}

export function parseRecordPage(value: string | null): number {
  const page = Number(value);
  return Number.isSafeInteger(page) && page > 0 ? page : 1;
}

/** Return only to this app's records page, never a supplied external URL. */
export function recordsReturnHref(value: string | null, fallback = "/records?type=flight"): string {
  if (!value) return fallback;
  try {
    const url = new URL(value, "https://azmark.invalid");
    if (url.origin === "https://azmark.invalid" && url.pathname === "/records") return `${url.pathname}${url.search}`;
  } catch { /* Invalid destinations fall back to the record list. */ }
  return fallback;
}
