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

// Trains and other transports share the same lifecycle values, but each has
// its own copy in the dictionaries.
const RECORD_STATUS: Record<
  "trains" | "transports",
  Record<string, { variant: BadgeVariant; key: TranslationKey }>
> = {
  trains: {
    scheduled: { variant: "neutral", key: "trains.status.scheduled" },
    completed: { variant: "success", key: "trains.status.completed" },
    cancelled: { variant: "danger", key: "trains.status.cancelled" },
  },
  transports: {
    scheduled: { variant: "neutral", key: "transports.status.scheduled" },
    completed: { variant: "success", key: "transports.status.completed" },
    cancelled: { variant: "danger", key: "transports.status.cancelled" },
  },
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

function RecordStatusBadge({
  status,
  kind,
}: {
  status: string;
  kind: keyof typeof RECORD_STATUS;
}) {
  const { t } = useI18n();
  const map = RECORD_STATUS[kind][status];
  return <Badge variant={map?.variant ?? "neutral"}>{map ? t(map.key) : status}</Badge>;
}

export function TrainStatusBadge({ status }: { status: string }) {
  return <RecordStatusBadge status={status} kind="trains" />;
}

export function TransportStatusBadge({ status }: { status: string }) {
  return <RecordStatusBadge status={status} kind="transports" />;
}
