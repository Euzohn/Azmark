"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
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
        <Input
          value={form.carrier}
          onChange={(e) => set("carrier", e.target.value)}
          placeholder="Cathay Pacific"
        />
      </Field>
      <Field label={t("flights.origin")}>
        <Input
          value={form.origin}
          onChange={(e) => set("origin", e.target.value)}
          placeholder="HKG"
        />
      </Field>
      <Field label={t("flights.destination")}>
        <Input
          value={form.destination}
          onChange={(e) => set("destination", e.target.value)}
          placeholder="SIN"
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
