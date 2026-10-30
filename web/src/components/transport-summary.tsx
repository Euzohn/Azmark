"use client";

import { ArrowRight, Bus } from "lucide-react";
import { useState } from "react";

import { TransportStatusBadge } from "@/components/status-badge";
import { TripLinkCard } from "@/components/trip-link-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatZonedDateTime } from "@/lib/datetime";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { OtherTransport } from "@/lib/types";

const VEHICLE_TYPES: Record<string, TranslationKey> = {
  bus: "transports.vehicleType.bus",
  ferry: "transports.vehicleType.ferry",
  taxi: "transports.vehicleType.taxi",
  rideshare: "transports.vehicleType.rideshare",
  car: "transports.vehicleType.car",
  bike: "transports.vehicleType.bike",
  walk: "transports.vehicleType.walk",
  cruise: "transports.vehicleType.cruise",
  other: "transports.vehicleType.other",
};

const CREDENTIAL_TYPES: Record<string, TranslationKey> = {
  id_card: "flights.credentialType.id_card",
  passport: "flights.credentialType.passport",
  hk_macau_permit: "flights.credentialType.hk_macau_permit",
  taiwan_permit: "flights.credentialType.taiwan_permit",
  other: "flights.credentialType.other",
};

/**
 * Read-only detail for the "other transport" records (spec #17), mirroring
 * FlightSummary so every record type has the same view → edit flow. Ticket
 * number, booking reference and purchase credential stay masked (spec #45).
 */
export function TransportSummary({ transport }: { transport: OtherTransport }) {
  const { t, locale } = useI18n();
  const [showSensitive, setShowSensitive] = useState(false);

  const format = (value: string | null, timezone: string | null) =>
    formatZonedDateTime(value, locale, timezone);
  const label = (value: string | null, map: Record<string, TranslationKey>) => {
    if (!value) return null;
    const key = map[value];
    return key ? t(key) : value;
  };

  const vehicleType = label(transport.vehicle_type, VEHICLE_TYPES);
  const fields: [TranslationKey, string | null][] = [
    ["transports.seat", transport.seat],
    ["transports.departureStation", transport.departure_gate],
    ["transports.arrivalStation", transport.arrival_gate],
    ["transports.distance", transport.distance],
  ];

  return (
    <>
      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 md:px-7">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Bus className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate text-sm font-semibold">
                  {transport.service_number ?? "—"}
                </span>
                {vehicleType ? <Badge variant="neutral">{vehicleType}</Badge> : null}
              </div>
              {transport.carrier ? (
                <div className="truncate text-xs text-muted-foreground">{transport.carrier}</div>
              ) : null}
            </div>
          </div>
          <TransportStatusBadge status={transport.status} />
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)_2rem_minmax(0,1fr)] items-start gap-3 px-5 py-7 md:gap-8 md:px-7 md:py-9">
          <div className="min-w-0">
            <div className="mb-2 text-xs text-muted-foreground">{t("transports.origin")}</div>
            <div className="break-words text-2xl font-semibold tracking-tight md:text-4xl">
              {transport.origin ?? "—"}
            </div>
            <div className="mt-5 text-sm font-medium tabular-nums">
              {format(transport.departure_time, transport.departure_timezone)}
            </div>
            <div className="mt-1 break-words text-xs text-muted-foreground">
              {transport.departure_timezone}
            </div>
          </div>
          <div className="mt-6 flex flex-col items-center gap-3 text-primary md:mt-8">
            <Bus className="h-5 w-5" />
            <ArrowRight className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="mb-2 text-xs text-muted-foreground">
              {t("transports.destination")}
            </div>
            <div className="break-words text-2xl font-semibold tracking-tight md:text-4xl">
              {transport.destination ?? "—"}
            </div>
            <div className="mt-5 text-sm font-medium tabular-nums">
              {format(transport.arrival_time, transport.arrival_timezone)}
            </div>
            <div className="mt-1 break-words text-xs text-muted-foreground">
              {transport.arrival_timezone}
            </div>
          </div>
        </div>

        <div className="border-t border-border px-5 py-3 text-xs text-muted-foreground md:px-7">
          {t("transports.detail.localTime")}
        </div>

        {transport.actual_departure_time || transport.actual_arrival_time ? (
          <dl className="grid gap-4 border-t border-border bg-muted/30 px-5 py-4 sm:grid-cols-2 md:px-7">
            <DetailField
              label={t("transports.actualDepartureTime")}
              value={format(transport.actual_departure_time, transport.departure_timezone)}
            />
            <DetailField
              label={t("transports.actualArrivalTime")}
              value={format(transport.actual_arrival_time, transport.arrival_timezone)}
            />
          </dl>
        ) : null}
      </section>

      {transport.trip_id ? (
        <TripLinkCard tripId={transport.trip_id} label={t("transports.trip")} />
      ) : null}

      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="mb-5 text-sm font-semibold">{t("transports.section.transport")}</h2>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-5">
          {fields.map(([key, value]) => (
            <DetailField key={key} label={t(key)} value={value} />
          ))}
        </dl>
      </section>

      <section className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-sm font-semibold">{t("transports.section.ticket")}</h2>
          <Button
            variant="ghost"
            size="sm"
            aria-pressed={showSensitive}
            onClick={() => setShowSensitive((show) => !show)}
          >
            {t(showSensitive ? "common.hide" : "common.show")}
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {t("transports.detail.ticketHint")}
        </p>
        <dl className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3">
          <DetailField
            label={t("transports.price")}
            value={
              transport.price ? `${transport.price} ${transport.currency ?? ""}`.trim() : null
            }
          />
          <DetailField
            label={t("transports.purchaseCredentialType")}
            value={label(transport.purchase_credential_type, CREDENTIAL_TYPES)}
          />
          {(
            [
              ["transports.bookingReference", transport.booking_reference],
              ["transports.ticketNumber", transport.ticket_number],
              ["transports.purchaseCredential", transport.purchase_credential],
            ] as [TranslationKey, string | null][]
          ).map(([key, value]) => (
            <DetailField
              key={key}
              label={t(key)}
              value={value ? (showSensitive ? value : "••••••") : null}
            />
          ))}
        </dl>
      </section>

      {transport.notes ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <h2 className="mb-3 text-sm font-semibold">{t("transports.notes")}</h2>
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">
            {transport.notes}
          </p>
        </section>
      ) : null}
    </>
  );
}

function DetailField({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1.5 break-words text-sm font-medium">{value || "—"}</dd>
    </div>
  );
}
