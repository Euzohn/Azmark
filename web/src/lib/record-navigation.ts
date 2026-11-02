import type { RecordSort } from "./types";

export function parseRecordSort(value: string | null): RecordSort {
  return value === "oldest" || value === "departure" || value === "arrival" || value === "created" ? value : "newest";
}

export function parseRecordPage(value: string | null): number {
  const page = Number(value);
  return Number.isSafeInteger(page) && page > 0 ? page : 1;
}

/** Return only to a whitelisted in-app list page, never a supplied external URL. */
function internalReturnHref(value: string | null, pathname: string, fallback: string): string {
  if (!value) return fallback;
  try {
    const url = new URL(value, "https://azmark.invalid");
    if (url.origin === "https://azmark.invalid" && url.pathname === pathname) return `${url.pathname}${url.search}`;
  } catch { /* Invalid destinations fall back to the list. */ }
  return fallback;
}

/** Return only to this app's records page, never a supplied external URL. */
export function recordsReturnHref(value: string | null, fallback = "/records?type=flight"): string {
  return internalReturnHref(value, "/records", fallback);
}

/** Return only to this app's hotels page, never a supplied external URL. */
export function hotelsReturnHref(value: string | null): string {
  return internalReturnHref(value, "/hotels", "/hotels");
}
