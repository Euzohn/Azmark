"use client";

import { Badge, type BadgeVariant } from "@/components/ui/badge";
import { useI18n, type TranslationKey } from "@/lib/i18n";

const FLIGHT_STATUS: Record<string, { variant: BadgeVariant; key: TranslationKey }> = {
  scheduled: { variant: "neutral", key: "flights.status.scheduled" },
  completed: { variant: "success", key: "flights.status.completed" },
  cancelled: { variant: "danger", key: "flights.status.cancelled" },
};

const TRIP_STATUS: Record<string, { variant: BadgeVariant; key: TranslationKey }> = {
  planned: { variant: "neutral", key: "trips.status.planned" },
  ongoing: { variant: "primary", key: "trips.status.ongoing" },
  completed: { variant: "success", key: "trips.status.completed" },
};

export function FlightStatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const map = FLIGHT_STATUS[status] ?? { variant: "neutral" as BadgeVariant, key: undefined };
  return <Badge variant={map.variant}>{map.key ? t(map.key) : status}</Badge>;
}

export function TripStatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const map = TRIP_STATUS[status] ?? { variant: "neutral" as BadgeVariant, key: undefined };
  return <Badge variant={map.variant}>{map.key ? t(map.key) : status}</Badge>;
}
