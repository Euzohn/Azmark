const FALLBACK_TIMEZONES = [
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
    return zones.length > 0 ? zones : FALLBACK_TIMEZONES;
  } catch {
    return FALLBACK_TIMEZONES;
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
