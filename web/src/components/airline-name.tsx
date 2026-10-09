"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface AirlineNameProps {
  code: string | null;
  fallback: string | null;
}

export function AirlineName({ code, fallback }: AirlineNameProps) {
  const { locale } = useI18n();
  const { data } = useQuery({
    queryKey: ["airline", code],
    queryFn: () => api.getAirlineByCode(code!),
    enabled: Boolean(code),
    staleTime: Infinity,
  });

  if (!code || !data) return fallback ?? "";
  return locale === "zh-CN" ? (data.name_zh ?? data.name) : data.name;
}
