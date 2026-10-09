"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { Loader2, Wand2 } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Flight, FlightInput } from "@/lib/types";

function toLocalInput(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

// 航班日期已过 → 默认「已完成」，否则「计划中」。空/非法返回 null 表示不干预。
function autoStatus(departure: string): string | null {
  if (!departure) return null;
  const date = new Date(departure);
  if (Number.isNaN(date.getTime())) return null;
  return date.getTime() < Date.now() ? "completed" : "scheduled";
}

interface FlightFormProps {
  initial?: Flight;
  submitting?: boolean;
  onSubmit: (data: FlightInput) => void | Promise<void>;
}

export function FlightForm({ initial, submitting, onSubmit }: FlightFormProps) {
  const { t, locale } = useI18n();
  const [form, setForm] = useState({
    service_number: initial?.service_number ?? "",
    carrier: initial?.carrier ?? "",
    origin: initial?.origin ?? "",
    destination: initial?.destination ?? "",
    departure_time: toLocalInput(initial?.departure_time),
    arrival_time: toLocalInput(initial?.arrival_time),
    actual_departure_time: toLocalInput(initial?.actual_departure_time),
    actual_arrival_time: toLocalInput(initial?.actual_arrival_time),
    seat: initial?.seat ?? "",
    departure_terminal: initial?.departure_terminal ?? "",
    departure_gate: initial?.departure_gate ?? "",
    arrival_terminal: initial?.arrival_terminal ?? "",
    arrival_gate: initial?.arrival_gate ?? "",
    status: initial?.status ?? "scheduled",
    price: initial?.price ?? "",
    currency: initial?.currency ?? "CNY",
    distance: initial?.distance ?? "",
    ticket_number: initial?.ticket_number ?? "",
    booking_reference: initial?.booking_reference ?? "",
    purchase_credential: initial?.purchase_credential ?? "",
    notes: initial?.notes ?? "",
    trip_id: initial?.trip_id ?? "",
  });

  const { data: trips } = useQuery({
    queryKey: ["trips"],
    queryFn: () => api.listTrips(),
  });

  const [lookupStatus, setLookupStatus] = useState<"idle" | "running" | "ok" | "local" | "error">(
    "idle",
  );
  const [lookupSource, setLookupSource] = useState<string | null>(null);
  const [lookupDate, setLookupDate] = useState(
    initial?.departure_time?.slice(0, 10) || new Date().toISOString().slice(0, 10),
  );
  const [statusTouched, setStatusTouched] = useState(Boolean(initial));

  const set = (key: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  // 变更起飞时间时同步推断状态（用户手动改过状态则不覆盖）。
  const setDepartureTime = (value: string) => {
    setForm((prev) => {
      const next = { ...prev, departure_time: value };
      if (!statusTouched) {
        const status = autoStatus(value);
        if (status) next.status = status;
      }
      return next;
    });
  };

  const fetchAirports = useCallback(
    async (query: string) => {
      const airports = await api.searchAirports(query);
      return airports.map((airport) => {
        const name = locale === "zh-CN" ? (airport.name_zh ?? airport.name) : airport.name;
        const city = locale === "zh-CN" ? (airport.city_zh ?? airport.city) : airport.city;
        return {
          value: airport.iata,
          label: `${airport.iata} · ${name}`,
          hint: [city, airport.country].filter(Boolean).join(", ") || undefined,
        };
      });
    },
    [locale],
  );

  const fetchAirlines = useCallback(
    async (query: string) => {
      const airlines = await api.searchAirlines(query);
      return airlines.map((airline) => {
        const name = locale === "zh-CN" ? (airline.name_zh ?? airline.name) : airline.name;
        return {
          value: name,
          label: `${airline.iata} · ${name}`,
          hint: airline.country ?? undefined,
        };
      });
    },
    [locale],
  );

  // Infer the airline from the flight-number prefix (spec #38, local-only).
  useEffect(() => {
    const value = form.service_number.trim();
    if (!/^[A-Za-z0-9]{2,3}\d{1,4}$/.test(value) || form.carrier.trim()) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .lookupFlightNumber(value)
        .then((result) => {
          if (cancelled || !result.airline) return;
          const name =
            locale === "zh-CN"
              ? result.airline.name_zh ?? result.airline.name
              : result.airline.name;
          setForm((prev) => (prev.carrier.trim() ? prev : { ...prev, carrier: name }));
        })
        .catch(() => {
          // Lookup is best-effort; the user can always type the airline.
        });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [form.service_number, form.carrier, locale]);

  const runLookup = async () => {
    const number = form.service_number.trim();
    if (!/^[A-Za-z0-9]{2,3}\d{1,4}$/.test(number)) return;
    setLookupStatus("running");
    const datePart = lookupDate || new Date().toISOString().slice(0, 10);
    try {
      const result = await api.lookupFlight({ flight_number: number, date: datePart });
      setForm((prev) => {
        const next = { ...prev };
        const airlineName =
          locale === "zh-CN"
            ? (result.airline_name_zh ?? result.airline_name ?? "")
            : result.airline_name ?? "";
        if (airlineName && !next.carrier.trim()) next.carrier = airlineName;
        if (result.origin_iata && !next.origin.trim()) next.origin = result.origin_iata;
        if (result.destination_iata && !next.destination.trim())
          next.destination = result.destination_iata;
        if (result.departure_time && !next.departure_time) {
          next.departure_time = toLocalInput(result.departure_time);
          if (!statusTouched) {
            const status = autoStatus(next.departure_time);
            if (status) next.status = status;
          }
        }
        if (result.arrival_time && !next.arrival_time)
          next.arrival_time = toLocalInput(result.arrival_time);
        if (result.actual_departure_time && !next.actual_departure_time)
          next.actual_departure_time = toLocalInput(result.actual_departure_time);
        if (result.actual_arrival_time && !next.actual_arrival_time)
          next.actual_arrival_time = toLocalInput(result.actual_arrival_time);
        if (result.distance && !next.distance) next.distance = String(result.distance);
        return next;
      });
      if (result.source && result.source !== "local") {
        setLookupSource(result.source);
        setLookupStatus("ok");
      } else {
        setLookupStatus("local");
      }
    } catch {
      setLookupStatus("error");
    }
  };

  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    if (!form.origin.trim() || !form.destination.trim()) {
      setFormError(t("flights.requiredRoute"));
      return;
    }
    const data: FlightInput = {
      service_number: form.service_number || null,
      carrier: form.carrier || null,
      origin: form.origin || null,
      destination: form.destination || null,
      departure_time: fromLocalInput(form.departure_time),
      arrival_time: fromLocalInput(form.arrival_time),
      actual_departure_time: fromLocalInput(form.actual_departure_time),
      actual_arrival_time: fromLocalInput(form.actual_arrival_time),
      seat: form.seat || null,
      departure_terminal: form.departure_terminal || null,
      departure_gate: form.departure_gate || null,
      arrival_terminal: form.arrival_terminal || null,
      arrival_gate: form.arrival_gate || null,
      status: form.status,
      price: form.price || null,
      currency: form.currency || null,
      distance: form.distance || null,
      ticket_number: form.ticket_number || null,
      booking_reference: form.booking_reference || null,
      purchase_credential: form.purchase_credential || null,
      notes: form.notes || null,
      trip_id: form.trip_id || null,
    };
    void onSubmit(data);
  };

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
      <Field label={t("flights.serviceNumber")}>
        <div className="flex gap-2">
          <Input
            value={form.service_number}
            onChange={(e) => set("service_number", e.target.value)}
            placeholder="CX659"
            className="flex-1"
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => void runLookup()}
            disabled={
              lookupStatus === "running" ||
              !/^[A-Za-z0-9]{2,3}\d{1,4}$/.test(form.service_number.trim())
            }
            title={t("flights.lookup")}
            aria-label={t("flights.lookup")}
          >
            {lookupStatus === "running" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Wand2 className="h-4 w-4" />
            )}
          </Button>
        </div>
        {lookupStatus !== "idle" ? (
          <p className="mt-1.5 text-xs text-muted-foreground">
            {lookupStatus === "running" ? t("flights.lookupRunning") : null}
            {lookupStatus === "ok"
              ? t("flights.lookupRemote", { source: lookupSource ?? "" })
              : null}
            {lookupStatus === "local" ? (
              <>
                {t("flights.lookupLocal")}{" "}
                <Link href="/settings" className="text-primary hover:underline">
                  {t("nav.settings")}
                </Link>
              </>
            ) : null}
            {lookupStatus === "error" ? t("flights.lookupFailed") : null}
          </p>
        ) : null}
      </Field>
      <Field label={t("flights.lookupDate")}>
        <Input
          type="date"
          value={lookupDate}
          onChange={(e) => setLookupDate(e.target.value)}
        />
      </Field>
      <Field label={t("flights.carrier")}>
        <Combobox
          value={form.carrier}
          onChange={(value) => set("carrier", value)}
          fetchOptions={fetchAirlines}
          placeholder={t("flights.airlineSearch")}
          emptyText={t("flights.noResults")}
        />
      </Field>
      <Field label={t("flights.origin")} required>
        <Combobox
          value={form.origin}
          onChange={(value) => set("origin", value)}
          fetchOptions={fetchAirports}
          placeholder={t("flights.airportSearch")}
          emptyText={t("flights.noResults")}
        />
      </Field>
      <Field label={t("flights.destination")} required>
        <Combobox
          value={form.destination}
          onChange={(value) => set("destination", value)}
          fetchOptions={fetchAirports}
          placeholder={t("flights.airportSearch")}
          emptyText={t("flights.noResults")}
        />
      </Field>
      <Field label={t("flights.departureTime")}>
        <Input
          type="datetime-local"
          value={form.departure_time}
          onChange={(e) => setDepartureTime(e.target.value)}
        />
      </Field>
      <Field label={t("flights.arrivalTime")}>
        <Input
          type="datetime-local"
          value={form.arrival_time}
          onChange={(e) => set("arrival_time", e.target.value)}
        />
      </Field>
      <Field label={t("flights.actualDepartureTime")}>
        <Input
          type="datetime-local"
          value={form.actual_departure_time}
          onChange={(e) => set("actual_departure_time", e.target.value)}
        />
      </Field>
      <Field label={t("flights.actualArrivalTime")}>
        <Input
          type="datetime-local"
          value={form.actual_arrival_time}
          onChange={(e) => set("actual_arrival_time", e.target.value)}
        />
      </Field>
      <Field label={t("flights.seat")}>
        <Input value={form.seat} onChange={(e) => set("seat", e.target.value)} placeholder="32A" />
      </Field>
      <Field label={t("flights.status")}>
        <Select
          value={form.status}
          onChange={(e) => {
            setStatusTouched(true);
            set("status", e.target.value);
          }}
        >
          <option value="scheduled">{t("flights.status.scheduled")}</option>
          <option value="completed">{t("flights.status.completed")}</option>
          <option value="cancelled">{t("flights.status.cancelled")}</option>
        </Select>
      </Field>
      <Field label={t("flights.trip")}>
        <Select
          value={form.trip_id}
          onChange={(e) => set("trip_id", e.target.value)}
        >
          <option value="">{t("flights.tripNone")}</option>
          {trips?.items.map((trip) => (
            <option key={trip.id} value={trip.id}>
              {trip.name || `${trip.origin ?? ""} → ${trip.destination ?? ""}`}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("flights.departureTerminal")}>
        <Input
          value={form.departure_terminal}
          onChange={(e) => set("departure_terminal", e.target.value)}
          placeholder="T1"
        />
      </Field>
      <Field label={t("flights.departureGate")}>
        <Input
          value={form.departure_gate}
          onChange={(e) => set("departure_gate", e.target.value)}
          placeholder="23"
        />
      </Field>
      <Field label={t("flights.arrivalTerminal")}>
        <Input
          value={form.arrival_terminal}
          onChange={(e) => set("arrival_terminal", e.target.value)}
          placeholder="T4"
        />
      </Field>
      <Field label={t("flights.arrivalGate")}>
        <Input
          value={form.arrival_gate}
          onChange={(e) => set("arrival_gate", e.target.value)}
          placeholder="B12"
        />
      </Field>
      <Field label={t("flights.price")}>
        <Input
          type="number"
          step="0.01"
          value={form.price}
          onChange={(e) => set("price", e.target.value)}
        />
      </Field>
      <Field label={t("flights.currency")}>
        <Input
          value={form.currency}
          maxLength={3}
          onChange={(e) => set("currency", e.target.value.toUpperCase())}
        />
      </Field>
      <Field label={t("flights.distance")}>
        <Input
          type="number"
          step="0.01"
          min="0"
          value={form.distance}
          onChange={(e) => set("distance", e.target.value)}
        />
      </Field>
      <Field label={t("flights.ticketNumber")}>
        <Input
          value={form.ticket_number}
          onChange={(e) => set("ticket_number", e.target.value)}
          placeholder="160-1234567890"
        />
      </Field>
      <Field label={t("flights.purchaseCredential")} className="md:col-span-2">
        <Input
          value={form.purchase_credential}
          onChange={(e) => set("purchase_credential", e.target.value)}
          placeholder="E12345678"
        />
      </Field>
      <Field label={t("flights.bookingReference")} className="md:col-span-2">
        <Input
          value={form.booking_reference}
          onChange={(e) => set("booking_reference", e.target.value)}
          placeholder="ABCDEF"
          maxLength={6}
        />
      </Field>
      <Field label={t("flights.notes")} className="md:col-span-2">
        <Textarea
          rows={3}
          value={form.notes}
          onChange={(e) => set("notes", e.target.value)}
        />
      </Field>
      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" disabled={submitting}>
          {t("common.save")}
        </Button>
        {formError ? <span className="text-sm text-danger">{formError}</span> : null}
      </div>
    </form>
  );
}

function Field({
  label,
  required,
  className,
  children,
}: {
  label: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={className}>
      <Label className="mb-1.5 block">
        {label}
        {required ? (
          <span className="text-danger" aria-hidden="true">
            *
          </span>
        ) : null}
      </Label>
      {children}
    </div>
  );
}
