"use client";

import { useQuery } from "@tanstack/react-query";
import { Crown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const ALLIANCE_LABELS = {
  star_alliance: "alliance.star_alliance",
  skyteam: "alliance.skyteam",
  oneworld: "alliance.oneworld",
} as const;

interface AllianceBadgeProps {
  code: string | null;
  className?: string;
}

export function AllianceBadge({ code, className }: AllianceBadgeProps) {
  const { t } = useI18n();
  const { data } = useQuery({
    queryKey: ["airline", code],
    queryFn: () => api.getAirlineByCode(code!),
    enabled: Boolean(code),
    staleTime: Infinity,
  });

  const alliance = data?.alliance;
  if (!alliance) return null;

  const key = ALLIANCE_LABELS[alliance as keyof typeof ALLIANCE_LABELS];
  if (!key) return null;

  return (
    <Badge variant="neutral" className={cn("gap-1", className)}>
      <Crown className="h-3 w-3 text-primary" aria-hidden="true" />
      {t(key)}
    </Badge>
  );
}