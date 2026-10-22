"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * Records store origin/destination as IATA codes (that is what flight lookups
 * return), which renders as "SZX" in lists. This resolves a 3-letter code to
 * the airport's localized name and shows the code in a tooltip instead.
 *
 * Anything that does not look like an IATA code (station names, free text) is
 * rendered as-is, so the same component works for trains and other transport.
 */
const IATA_CODE = /^[A-Z]{3}$/;

interface AirportNameProps {
  value: string | null | undefined;
  className?: string;
  /** Show the IATA code next to the airport name. */
  showCode?: boolean;
  codeClassName?: string;
}

export function AirportName({
  value,
  className,
  showCode = false,
  codeClassName,
}: AirportNameProps) {
  const { locale } = useI18n();
  const code = value?.trim().toUpperCase() ?? "";
  const isCode = IATA_CODE.test(code);
  const { data } = useQuery({
    queryKey: ["airport", code],
    queryFn: () => api.getAirportByIata(code),
    enabled: isCode,
    staleTime: Infinity,
    retry: false,
  });

  if (!value) return "";
  if (!isCode || !data) return <span className={className}>{value}</span>;

  const name = locale === "zh-CN" ? (data.name_zh ?? data.name) : data.name;
  const tooltip = [data.iata, data.name, data.name_zh].filter(Boolean).join(" · ");

  return (
    <span className={className} title={tooltip}>
      {name}
      {showCode ? (
        <span className={cn("ml-1.5 font-normal text-muted-foreground", codeClassName)}>
          {data.iata}
        </span>
      ) : null}
    </span>
  );
}
