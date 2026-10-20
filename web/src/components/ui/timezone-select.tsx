"use client";

import { Select } from "@/components/ui/select";
import { useI18n } from "@/lib/i18n";
import { TIMEZONES } from "@/lib/timezones";

interface TimezoneSelectProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

/**
 * IANA timezone picker used by the flight / train / transport forms.
 *
 * Everything selectable is a real IANA name, so a record can never be saved
 * with the "+08:00" style value VariFlight returns (the backend normalizes
 * those on write as well). A value that is neither blank nor in the list — an
 * offset written before the backend normalized the column — is surfaced as an
 * extra option instead of being silently dropped, so an old record still shows
 * what it actually holds.
 */
export function TimezoneSelect({ value, onChange, className }: TimezoneSelectProps) {
  const { t } = useI18n();
  const unknown = value.trim() !== "" && !TIMEZONES.includes(value);
  return (
    <Select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={className}
    >
      <option value="">{t("common.none")}</option>
      {unknown ? <option value={value}>{value}</option> : null}
      {TIMEZONES.map((zone) => (
        <option key={zone} value={zone}>
          {zone}
        </option>
      ))}
    </Select>
  );
}
