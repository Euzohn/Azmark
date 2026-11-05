"use client";

import { useMemo } from "react";

import { Select } from "@/components/ui/select";
import { allCurrencyCodes, COMMON_CURRENCIES } from "@/lib/currencies";
import { useI18n } from "@/lib/i18n";

interface CurrencySelectProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  /** Allow clearing the value (optional price fields do; the profile does not). */
  allowEmpty?: boolean;
  required?: boolean;
  disabled?: boolean;
  id?: string;
}

function displayNamesFor(locale: string): Intl.DisplayNames | null {
  try {
    return new Intl.DisplayNames([locale], { type: "currency" });
  } catch {
    return null;
  }
}

/** "CNY · 人民币" / "CNY · Chinese Yuan"; falls back to the bare code. */
function currencyLabel(names: Intl.DisplayNames | null, code: string): string {
  if (!names) return code;
  try {
    const name = names.of(code);
    return name && name.toLowerCase() !== code.toLowerCase() ? `${code} · ${name}` : code;
  } catch {
    // Non-ISO values (e.g. a legacy "RMB") are not in the display table.
    return code;
  }
}

/**
 * Currency picker backed by ISO 4217 codes (spec #19).
 *
 * Replaces free-text three-letter input: "RMB" is not a currency code, so it
 * silently broke totals. Common codes are grouped first; the rest of the
 * runtime's ISO table follows. A value already stored on the record is always
 * kept as an option so editing never changes data behind the user's back.
 */
export function CurrencySelect({
  value,
  onChange,
  className,
  allowEmpty = true,
  required,
  disabled,
  id,
}: CurrencySelectProps) {
  const { locale, t } = useI18n();
  const names = useMemo(() => displayNamesFor(locale), [locale]);

  const { common, others } = useMemo(() => {
    const current = value.trim().toUpperCase();
    const commonCodes: string[] = [...COMMON_CURRENCIES];
    if (current && !commonCodes.includes(current)) commonCodes.push(current);
    const commonSet = new Set(commonCodes);
    return {
      common: commonCodes,
      others: allCurrencyCodes().filter((code) => !commonSet.has(code)),
    };
  }, [value]);

  return (
    <Select
      id={id}
      className={className}
      value={value.trim().toUpperCase()}
      onChange={(event) => onChange(event.target.value)}
      required={required}
      disabled={disabled}
    >
      {allowEmpty ? <option value="">{t("common.none")}</option> : null}
      <optgroup label={t("currency.common")}>
        {common.map((code) => (
          <option key={code} value={code}>
            {currencyLabel(names, code)}
          </option>
        ))}
      </optgroup>
      {others.length > 0 ? (
        <optgroup label={t("currency.other")}>
          {others.map((code) => (
            <option key={code} value={code}>
              {currencyLabel(names, code)}
            </option>
          ))}
        </optgroup>
      ) : null}
    </Select>
  );
}
