"use client";

import { ArrowRight, Plane } from "lucide-react";
import { useState } from "react";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { AirportName } from "@/components/airport-name";
import { FlightStatusBadge } from "@/components/status-badge";
import { TripLinkCard } from "@/components/trip-link-card";
import { Button } from "@/components/ui/button";
import { formatZonedDateTime } from "@/lib/datetime";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Flight } from "@/lib/types";

export function FlightSummary({ flight }: { flight: Flight }) {
  const { t, locale } = useI18n();
  const [showSensitive, setShowSensitive] = useState(false);
  const format = (value: string | null, timezone: string | null) => formatZonedDateTime(value, locale, timezone);
  const cabinKeys: Record<string, TranslationKey> = { economy: "flights.cabin.economy", premium_economy: "flights.cabin.premium_economy", business: "flights.cabin.business", first: "flights.cabin.first" };
  const sections: { title: TranslationKey; fields: [TranslationKey, string | null][] }[] = [
    { title: "flights.section.airport", fields: [["flights.departureTerminal", flight.departure_terminal], ["flights.departureGate", flight.departure_gate], ["flights.arrivalTerminal", flight.arrival_terminal], ["flights.arrivalGate", flight.arrival_gate], ["flights.checkInDesk", flight.check_in_desk], ["flights.baggageBelt", flight.baggage_belt]] },
    { title: "flights.section.aircraft", fields: [["flights.seat", flight.seat], ["flights.cabinClass", flight.cabin_class ? (cabinKeys[flight.cabin_class] ? t(cabinKeys[flight.cabin_class]) : flight.cabin_class) : null], ["flights.aircraftModel", flight.aircraft_model], ["flights.aircraftReg", flight.aircraft_reg], ["flights.distance", flight.distance]] },
  ];

  return <>
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 md:px-7">
        <div className="flex items-center gap-3"><AirlineLogo code={flight.airline_code} className="h-9 w-9" /><div><div className="text-sm font-semibold">{flight.service_number ?? "—"}</div><div className="text-xs text-muted-foreground"><AirlineName code={flight.airline_code} fallback={flight.carrier} /></div></div></div>
        <FlightStatusBadge status={flight.status} />
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_2rem_minmax(0,1fr)] items-start gap-3 px-5 py-7 md:gap-8 md:px-7 md:py-9">
        <div className="min-w-0"><div className="mb-2 text-xs text-muted-foreground">{t("flights.origin")}</div><div className="break-words text-3xl font-semibold tracking-tight md:text-5xl">{flight.origin ?? "—"}</div><div className="mt-2 text-sm text-muted-foreground"><AirportName value={flight.origin} /></div><div className="mt-5 text-sm font-medium tabular-nums">{format(flight.departure_time, flight.departure_timezone)}</div><div className="mt-1 break-words text-xs text-muted-foreground">{flight.departure_timezone}</div></div>
        <div className="mt-8 flex flex-col items-center gap-3 text-primary"><Plane className="h-5 w-5" /><ArrowRight className="h-5 w-5" /></div>
        <div className="min-w-0"><div className="mb-2 text-xs text-muted-foreground">{t("flights.destination")}</div><div className="break-words text-3xl font-semibold tracking-tight md:text-5xl">{flight.destination ?? "—"}</div><div className="mt-2 text-sm text-muted-foreground"><AirportName value={flight.destination} /></div><div className="mt-5 text-sm font-medium tabular-nums">{format(flight.arrival_time, flight.arrival_timezone)}</div><div className="mt-1 break-words text-xs text-muted-foreground">{flight.arrival_timezone}</div></div>
      </div>
      <div className="border-t border-border px-5 py-3 text-xs text-muted-foreground md:px-7">{t("flights.detail.localTime")}</div>
      {flight.actual_departure_time || flight.actual_arrival_time ? <dl className="grid gap-4 border-t border-border px-5 py-4 sm:grid-cols-2 md:px-7"><DetailField label={t("flights.actualDepartureTime")} value={format(flight.actual_departure_time, flight.departure_timezone)} /><DetailField label={t("flights.actualArrivalTime")} value={format(flight.actual_arrival_time, flight.arrival_timezone)} /></dl> : null}
    </section>
    {flight.trip_id ? <TripLinkCard tripId={flight.trip_id} label={t("flights.trip")} /> : null}
    <div className="grid gap-5 md:grid-cols-2">
      {sections.map(({ title, fields }) => <section key={title} className="rounded-xl border border-border bg-card p-5"><h2 className="mb-5 text-sm font-semibold">{t(title)}</h2><dl className="grid grid-cols-2 gap-x-4 gap-y-5">{fields.map(([key, value]) => <DetailField key={key} label={t(key)} value={value} />)}</dl></section>)}
    </div>
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between gap-4"><h2 className="text-sm font-semibold">{t("flights.section.ticket")}</h2><Button variant="ghost" size="sm" aria-pressed={showSensitive} onClick={() => setShowSensitive((show) => !show)}>{t(showSensitive ? "common.hide" : "common.show")}</Button></div>
      <p className="mt-1 text-xs text-muted-foreground">{t("flights.detail.ticketHint")}</p>
      <dl className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3">
        <DetailField label={t("flights.price")} value={flight.price ? `${flight.price} ${flight.currency ?? ""}` : null} />
        {([["flights.bookingReference", flight.booking_reference], ["flights.ticketNumber", flight.ticket_number], ["flights.purchaseCredential", flight.purchase_credential]] as [TranslationKey, string | null][]).map(([key, value]) => <DetailField key={key} label={t(key)} value={value ? (showSensitive ? value : "••••••") : null} />)}
      </dl>
    </section>
    {flight.notes ? <section className="rounded-xl border border-border bg-card p-5"><h2 className="mb-3 text-sm font-semibold">{t("flights.notes")}</h2><p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">{flight.notes}</p></section> : null}
  </>;
}

function DetailField({ label, value }: { label: string; value: string | null }) {
  return <div className="min-w-0"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1.5 break-words text-sm font-medium">{value || "—"}</dd></div>;
}
