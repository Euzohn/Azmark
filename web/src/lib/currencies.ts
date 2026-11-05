/**
 * Currency codes are ISO 4217.
 *
 * The curated list covers what a traveller is most likely to record — it is
 * ordered by usefulness rather than alphabetically, so the common ones sit at
 * the top of the picker. Everything else comes from the runtime's ISO 4217
 * table via `Intl.supportedValuesOf("currency")`; this keeps the list complete
 * without hand-maintaining ~180 codes.
 */
export const COMMON_CURRENCIES = [
  "CNY",
  "USD",
  "EUR",
  "JPY",
  "HKD",
  "TWD",
  "GBP",
  "KRW",
  "SGD",
  "THB",
  "MYR",
  "AUD",
  "CAD",
  "NZD",
  "CHF",
  "SEK",
  "NOK",
  "DKK",
  "RUB",
  "INR",
  "IDR",
  "PHP",
  "VND",
  "AED",
  "SAR",
  "TRY",
  "BRL",
  "MXN",
  "ZAR",
  "ILS",
  "EGP",
  "MOP",
] as const;

const intl = Intl as typeof Intl & {
  supportedValuesOf?: (key: "currency") => string[];
};

/** All ISO 4217 codes the runtime knows, alphabetically. */
export function allCurrencyCodes(): string[] {
  const codes = intl.supportedValuesOf?.("currency") ?? [];
  return [...codes].sort((a, b) => a.localeCompare(b));
}
