"use client";

import { useCallback, useEffect, useState } from "react";

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

interface FlightFormProps {
  initial?: Flight;
  submitting?: boolean;
  onSubmit: (data: FlightInput) => void | Promise<void>;
}

export function FlightForm({ initial, submitting, onSubmit }: FlightFormProps) {
  const { t } = useI18n();
  const [form, setForm] = useState({
    service_number: initial?.service_number ?? "",
    carrier: initial?.carrier ?? "",
    origin: initial?.origin ?? "",
    destination: initial?.destination ?? "",
    departure_time: toLocalInput(initial?.departure_time),
    arrival_time: toLocalInput(initial?.arrival_time),
    seat: initial?.seat ?? "",
    terminal: initial?.terminal ?? "",
    gate: initial?.gate ?? "",
    status: initial?.status ?? "scheduled",
    price: initial?.price ?? "",
    currency: initial?.currency ?? "CNY",
    booking_reference: initial?.booking_reference ?? "",
    notes: initial?.notes ?? "",
  });

  const set = (key: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const fetchAirports = useCallback(async (query: string) => {
    const airports = await api.searchAirports(query);
    return airports.map((airport) => ({
      value: airport.iata,
      label: `${airport.iata} · ${airport.name}`,
      hint: [airport.city, airport.country].filter(Boolean).join(", ") || undefined,
    }));
  }, []);

  const fetchAirlines = useCallback(async (query: string) => {
    const airlines = await api.searchAirlines(query);
    return airlines.map((airline) => ({
      value: airline.name,
      label: `${airline.iata} · ${airline.name}`,
      hint: airline.country ?? undefined,
    }));
  }, []);

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
          const name = result.airline.name;
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
  }, [form.service_number, form.carrier]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data: FlightInput = {
      service_number: form.service_number || null,
      carrier: form.carrier || null,
      origin: form.origin || null,
      destination: form.destination || null,
      departure_time: fromLocalInput(form.departure_time),
      arrival_time: fromLocalInput(form.arrival_time),
      seat: form.seat || null,
      terminal: form.terminal || null,
      gate: form.gate || null,
      status: form.status,
      price: form.price || null,
      currency: form.currency || null,
      booking_reference: form.booking_reference || null,
      notes: form.notes || null,
    };
    void onSubmit(data);
  };

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
      <Field label={t("flights.serviceNumber")}>
        <Input
          value={form.service_number}
          onChange={(e) => set("service_number", e.target.value)}
          placeholder="CX659"
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
      <Field label={t("flights.origin")}>
        <Combobox
          value={form.origin}
          onChange={(value) => set("origin", value)}
          fetchOptions={fetchAirports}
          placeholder={t("flights.airportSearch")}
          emptyText={t("flights.noResults")}
        />
      </Field>
      <Field label={t("flights.destination")}>
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
          onChange={(e) => set("departure_time", e.target.value)}
        />
      </Field>
      <Field label={t("flights.arrivalTime")}>
        <Input
          type="datetime-local"
          value={form.arrival_time}
          onChange={(e) => set("arrival_time", e.target.value)}
        />
      </Field>
      <Field label={t("flights.seat")}>
        <Input value={form.seat} onChange={(e) => set("seat", e.target.value)} placeholder="32A" />
      </Field>
      <Field label={t("flights.status")}>
        <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
          <option value="scheduled">{t("flights.status.scheduled")}</option>
          <option value="completed">{t("flights.status.completed")}</option>
          <option value="cancelled">{t("flights.status.cancelled")}</option>
        </Select>
      </Field>
      <Field label={t("flights.terminal")}>
        <Input value={form.terminal} onChange={(e) => set("terminal", e.target.value)} />
      </Field>
      <Field label={t("flights.gate")}>
        <Input value={form.gate} onChange={(e) => set("gate", e.target.value)} />
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
      <Field label={t("flights.bookingReference")} className="md:col-span-2">
        <Input
          value={form.booking_reference}
          onChange={(e) => set("booking_reference", e.target.value)}
        />
      </Field>
      <Field label={t("flights.notes")} className="md:col-span-2">
        <Textarea
          rows={3}
          value={form.notes}
          onChange={(e) => set("notes", e.target.value)}
        />
      </Field>
      <div className="md:col-span-2">
        <Button type="submit" disabled={submitting}>
          {t("common.save")}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={className}>
      <Label className="mb-1.5 block">{label}</Label>
      {children}
    </div>
  );
}
