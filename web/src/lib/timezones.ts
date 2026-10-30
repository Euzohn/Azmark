/**
 * The zones offered first when the picker opens. `Intl.supportedValuesOf`
 * returns 400+ entries, so the list starts with the ones a traveller is most
 * likely to want and relies on search for everything else.
 */
export const COMMON_TIMEZONES = [
  "UTC",
  "Asia/Shanghai",
  "Asia/Hong_Kong",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Asia/Dubai",
  "Europe/London",
  "Europe/Paris",
  "America/New_York",
  "America/Los_Angeles",
  "Australia/Sydney",
];

function loadTimezones(): string[] {
  try {
    const zones = Intl.supportedValuesOf("timeZone");
    if (zones.length === 0) return COMMON_TIMEZONES;
    // Some runtimes leave "UTC" out of supportedValuesOf; keep it selectable.
    return zones.includes("UTC") ? zones : ["UTC", ...zones];
  } catch {
    return COMMON_TIMEZONES;
  }
}

/**
 * Every IANA timezone the browser knows about. Shared by the profile settings
 * page and the flight / train / transport forms so a record can never hold a
 * timezone the profile dropdown cannot express.
 */
export const TIMEZONES: string[] = loadTimezones();

/**
 * Starting timezone for a brand-new record: the traveller's profile setting,
 * or their browser's zone when the profile still holds the backend default
 * "UTC" (i.e. they never chose one) — "UTC" is a poor default for a traveller.
 */
export function defaultTimezone(profileTimezone?: string | null): string {
  if (profileTimezone && profileTimezone !== "UTC") return profileTimezone;
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || profileTimezone || "";
  } catch {
    return profileTimezone || "";
  }
}

const formatterCache = new Map<string, Intl.DateTimeFormat | null>();

function offsetFormatter(zone: string): Intl.DateTimeFormat | null {
  const cached = formatterCache.get(zone);
  if (cached !== undefined) return cached;
  let formatter: Intl.DateTimeFormat | null = null;
  try {
    formatter = new Intl.DateTimeFormat("en-US", {
      timeZone: zone,
      timeZoneName: "shortOffset",
    });
  } catch {
    formatter = null;
  }
  formatterCache.set(zone, formatter);
  return formatter;
}

/**
 * "UTC+8" / "UTC-5" / "UTC+5:30" for a zone at a given instant. Returns "" when
 * the runtime does not know the zone. Defaults to now, so a DST boundary picks
 * the offset in effect today.
 */
export function timezoneOffsetLabel(zone: string, at: Date = new Date()): string {
  const formatter = offsetFormatter(zone);
  if (!formatter) return "";
  try {
    const raw =
      formatter.formatToParts(at).find((part) => part.type === "timeZoneName")?.value ?? "";
    // Intl returns "GMT+8" / "GMT-5:30" / "GMT" for UTC.
    if (!raw) return "";
    if (raw === "GMT" || raw === "UTC") return "UTC+0";
    return raw.replace(/^(GMT|UTC)/, "UTC");
  } catch {
    return "";
  }
}

/** "+05:30" / "+5" / "-8" → canonical "+5:30" / "+5" / "-8". */
function normalizeOffset(raw: string): string {
  const match = raw.match(/^([+-])(\d{1,2})(?::?(\d{2}))?$/);
  if (!match) return raw;
  const [, sign, hours, minutes] = match;
  const hour = Number(hours);
  const minute = Number(minutes ?? 0);
  if (hour > 14 || minute > 59) return raw;
  return `${sign}${hour}${minute ? `:${String(minute).padStart(2, "0")}` : ""}`;
}

/**
 * Turn a search box value into a UTC offset target. Accepts "+8", "-5",
 * "utc+8", "gmt-5", "utc5", "utc+5:30". A bare number stays a name search so
 * "8" does not unexpectedly match every +8 zone.
 */
export function parseOffsetQuery(query: string): string | null {
  const match = query.trim().toLowerCase().match(/^(?:(utc|gmt)\s*)?([+-])?(\d{1,2})(?::?(\d{2}))?$/);
  if (!match) return null;
  const [, prefix, sign, hours, minutes] = match;
  // Without a sign or a utc/gmt prefix the input is ambiguous.
  if (!prefix && !sign) return null;
  return normalizeOffset(`${sign ?? "+"}${hours}${minutes ? `:${minutes}` : ""}`);
}

/**
 * Filter the IANA list by name or UTC offset.
 *
 * Name matching is case-insensitive and treats "_" as a space, so "new york"
 * finds "America/New_York". Offset matching handles "+8", "utc+8" and
 * "utc+5:30" via {@link parseOffsetQuery}.
 */
export function filterTimezones(query: string, zones: string[] = TIMEZONES): string[] {
  const raw = query.trim().toLowerCase();
  if (!raw) return zones;
  const spaced = raw.replace(/_/g, " ");
  const offset = parseOffsetQuery(raw);
  return zones.filter((zone) => {
    const name = zone.toLowerCase();
    if (name.includes(raw) || name.replace(/_/g, " ").includes(spaced)) return true;
    if (offset === null) return false;
    return normalizeOffset(timezoneOffsetLabel(zone).replace(/^UTC/, "")) === offset;
  });
}