"use client";

import { ArrowRight, TrainFront } from "lucide-react";
import { useState } from "react";

import { TrainStatusBadge } from "@/components/status-badge";
import { TripLinkCard } from "@/components/trip-link-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatZonedDateTime } from "@/lib/datetime";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Train } from "@/lib/types";

const TRAIN_TYPES: Record<string, TranslationKey> = {
  high_speed: "trains.trainType.high_speed",
  intercity: "trains.trainType.intercity",
  conventional: "trains.trainType.conventional",
  night: "trains.trainType.night",
};

const CABIN_CLASSES: Record<string, TranslationKey> = {
  business: "trains.cabin.business",
  first: "trains.cabin.first",
  second: "trains.cabin.second",
  premium_soft: "trains.cabin.premium_soft",
  hard: "trains.cabin.hard",
  hard_seat: "trains.cabin.hard_seat",
  soft_seat: "trains.cabin.soft_seat",
};

const SEAT_TYPES: Record<string, TranslationKey> = {
  window: "trains.seatType.window",
  aisle: "trains.seatType.aisle",
  middle: "trains.seatType.middle",
  sleeper: "trains.seatType.sleeper",
  reclining: "trains.seatType.reclining",
  standing: "trains.seatType.standing",
};

const TICKET_TYPES: Record<string, TranslationKey> = {
  reserved: "trains.ticketType.reserved",
  standing: "trains.ticketType.standing",
  student: "trains.ticketType.student",
  child: "trains.ticketType.child",
};

const CREDENTIAL_TYPES: Record<string, TranslationKey> = {
  id_card: "flights.credentialType.id_card",
  passport: "flights.credentialType.passport",
  hk_macau_permit: "flights.credentialType.hk_macau_permit",
  taiwan_permit: "flights.credentialType.taiwan_permit",
  other: "flights.credentialType.other",
};

/**
 * Read-only train detail (spec #17), mirroring FlightSummary: the detail page
 * shows this until the traveller chooses to edit, so a saved record can be
 * read without opening a form. PNR / ticket number / purchase credential stay
 * masked until revealed (spec #45).
 */
export function TrainSummary({ train }: { train: Train }) {
  const { t, locale } = useI18n();
  const [showSensitive, setShowSensitive] = useState(false);

  const format = (value: string | null, timezone: string | null) =>
    formatZonedDateTime(value, locale, timezone);
  const label = (value: string | null, map: Record<string, TranslationKey>) => {
    if (!value) return null;
    const key = map[value];
    return key ? t(key) : value;
  };

  const trainType = label(train.train_type, TRAIN_TYPES);
  const sections: { title: TranslationKey; fields: [TranslationKey, string | null][] }[] = [
    {
      title: "trains.section.train",
      fields: [
        ["trains.trainType", trainType],
        ["trains.cabinClass", label(train.cabin_class, CABIN_CLASSES)],
        ["trains.carriage", train.carriage],
        ["trains.distance", train.distance],
      ],
    },
    {
      title: "trains.section.platformSeat",
      fields: [
        ["trains.departurePlatform", train.departure_gate],
        ["trains.arrivalPlatform", train.arrival_gate],
        ["trains.seat", train.seat],
        ["trains.seatType", label(train.seat_type, SEAT_TYPES)],
        ["trains.ticketType", label(train.ticket_type, TICKET_TYPES)],
      ],
    },
  ];

  return (
    <>
      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 md:px-7">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <TrainFront className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate text-sm font-semibold">
                  {train.service_number ?? "—"}
                </span>
                {trainType ? <Badge variant="neutral">{trainType}</Badge> : null}
              </div>
              {train.carrier ? (
                <div className="truncate text-xs text-muted-foreground">{train.carrier}</div>
              ) : null}
            </div>
          </div>
          <TrainStatusBadge status={train.status} />
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)_2rem_minmax(0,1fr)] items-start gap-3 px-5 py-7 md:gap-8 md:px-7 md:py-9">
          <div className="min-w-0">
            <div className="mb-2 text-xs text-muted-foreground">{t("trains.origin")}</div>
            <div className="break-words text-2xl font-semibold tracking-tight md:text-4xl">
              {train.origin ?? "—"}
            </div>
            <div className="mt-5 text-sm font-medium tabular-nums">
              {format(train.departure_time, train.departure_timezone)}
            </div>
            <div className="mt-1 break-words text-xs text-muted-foreground">
              {train.departure_timezone}
            </div>
          </div>
          <div className="mt-6 flex flex-col items-center gap-3 text-primary md:mt-8">
            <TrainFront className="h-5 w-5" />
            <ArrowRight className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="mb-2 text-xs text-muted-foreground">{t("trains.destination")}</div>
            <div className="break-words text-2xl font-semibold tracking-tight md:text-4xl">
              {train.destination ?? "—"}
            </div>
            <div className="mt-5 text-sm font-medium tabular-nums">
              {format(train.arrival_time, train.arrival_timezone)}
            </div>
            <div className="mt-1 break-words text-xs text-muted-foreground">
              {train.arrival_timezone}
            </div>
          </div>
        </div>

        <div className="border-t border-border px-5 py-3 text-xs text-muted-foreground md:px-7">
          {t("trains.detail.localTime")}
        </div>

        {train.actual_departure_time || train.actual_arrival_time ? (
          <dl className="grid gap-4 border-t border-border bg-muted/30 px-5 py-4 sm:grid-cols-2 md:px-7">
            <DetailField
              label={t("trains.actualDepartureTime")}
              value={format(train.actual_departure_time, train.departure_timezone)}
            />
            <DetailField
              label={t("trains.actualArrivalTime")}
              value={format(train.actual_arrival_time, train.arrival_timezone)}
            />
          </dl>
        ) : null}
      </section>

      {train.trip_id ? (
        <TripLinkCard tripId={train.trip_id} label={t("trains.trip")} />
      ) : null}

      <div className="grid gap-5 md:grid-cols-2">
        {sections.map(({ title, fields }) => (
          <section key={title} className="rounded-xl border border-border bg-card p-5">
            <h2 className="mb-5 text-sm font-semibold">{t(title)}</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-5">
              {fields.map(([key, value]) => (
                <DetailField key={key} label={t(key)} value={value} />
              ))}
            </dl>
          </section>
        ))}
      </div>

      <section className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-sm font-semibold">{t("trains.section.ticket")}</h2>
          <Button
            variant="ghost"
            size="sm"
            aria-pressed={showSensitive}
            onClick={() => setShowSensitive((show) => !show)}
          >
            {t(showSensitive ? "common.hide" : "common.show")}
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{t("trains.detail.ticketHint")}</p>
        <dl className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3">
          <DetailField
            label={t("trains.price")}
            value={train.price ? `${train.price} ${train.currency ?? ""}`.trim() : null}
          />
          <DetailField
            label={t("trains.purchaseCredentialType")}
            value={label(train.purchase_credential_type, CREDENTIAL_TYPES)}
          />
          {(
            [
              ["trains.bookingReference", train.booking_reference],
              ["trains.ticketNumber", train.ticket_number],
              ["trains.purchaseCredential", train.purchase_credential],
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

      {train.notes ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <h2 className="mb-3 text-sm font-semibold">{t("trains.notes")}</h2>
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">
            {train.notes}
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
