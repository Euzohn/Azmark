/**
 * Timezone-aware datetime helpers for the transport forms.
 *
 * Records store times as ISO-8601 instants (UTC). The forms use
 * `<input type="datetime-local">`, which holds a naive wall-clock string with no
 * offset. That string must represent the time in the *record's* IANA timezone
 * (departure_timezone / arrival_timezone), not the browser's timezone —
 * otherwise the displayed time disagrees with the timezone field and with the
 * local time reported by flight / train APIs.
 *
 * Every helper falls back to the browser's local timezone when `tz` is falsy, so
 * records without a timezone keep their previous behaviour.
 */

const pad = (n: number) => String(n).padStart(2, "0");

interface ZonedParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
}

function zonedParts(date: Date, tz: string): ZonedParts {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(date);
  const get = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? 0);
  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: get("hour"),
    minute: get("minute"),
    second: get("second"),
  };
}

/** Browser-local naive string — used when no timezone is known. */
export function toLocalInput(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

/** ISO instant → naive `YYYY-MM-DDTHH:mm` in `tz` (browser local when tz is empty). */
export function toZonedInput(
  value: string | null | undefined,
  tz?: string | null,
): string {
  if (!value) return "";
  if (!tz) return toLocalInput(value);
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  try {
    const p = zonedParts(date, tz);
    return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`;
  } catch {
    return toLocalInput(value);
  }
}

/** Offset (minutes) of `tz` from UTC at the given instant. */
function zonedOffsetMinutes(date: Date, tz: string): number {
  const p = zonedParts(date, tz);
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  return Math.round((asUtc - date.getTime()) / 60000);
}

/** Naive `YYYY-MM-DDTHH:mm` in `tz` → ISO instant (UTC). Browser local when tz is empty. */
export function fromZonedInput(value: string, tz?: string | null): string | null {
  if (!value || !value.includes("T")) return null;
  if (!tz) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
  }
  const normalized = value.length > 16 ? value.slice(0, 16) : value;
  const asUtc = new Date(`${normalized}:00Z`);
  if (Number.isNaN(asUtc.getTime())) return null;
  try {
    // Two passes so the offset is evaluated on the correct side of a DST edge.
    let offset = zonedOffsetMinutes(asUtc, tz);
    let instant = new Date(asUtc.getTime() - offset * 60000);
    offset = zonedOffsetMinutes(instant, tz);
    instant = new Date(asUtc.getTime() - offset * 60000);
    return Number.isNaN(instant.getTime()) ? null : instant.toISOString();
  } catch {
    return null;
  }
}

/** Calendar date (`YYYY-MM-DD`) of "now" in `tz` (browser local when tz is empty). */
export function todayInZone(tz?: string | null): string {
  if (!tz) {
    const now = new Date();
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  }
  try {
    const p = zonedParts(new Date(), tz);
    return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
  } catch {
    const now = new Date();
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  }
}
