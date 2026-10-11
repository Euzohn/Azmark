"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { OtherTransport, OtherTransportInput } from "@/lib/types";

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

function autoStatus(departure: string): string | null {
  if (!departure) return null;
  const date = new Date(departure);
  if (Number.isNaN(date.getTime())) return null;
  return date.getTime() < Date.now() ? "completed" : "scheduled";
}

interface TransportFormProps {
  initial?: OtherTransport;
  submitting?: boolean;
  onSubmit: (data: OtherTransportInput) => void | Promise<void>;
}

export function TransportForm({ initial, submitting, onSubmit }: TransportFormProps) {
  const { t } = useI18n();
  const [form, setForm] = useState({
    vehicle_type: initial?.vehicle_type ?? "",
    service_number: initial?.service_number ?? "",
    carrier: initial?.carrier ?? "",
    origin: initial?.origin ?? "",
    destination: initial?.destination ?? "",
    departure_time: toLocalInput(initial?.departure_time),
    arrival_time: toLocalInput(initial?.arrival_time),
    actual_departure_time: toLocalInput(initial?.actual_departure_time),
    actual_arrival_time: toLocalInput(initial?.actual_arrival_time),
    departure_gate: initial?.departure_gate ?? "",
    arrival_gate: initial?.arrival_gate ?? "",
    departure_timezone: initial?.departure_timezone ?? "",
    arrival_timezone: initial?.arrival_timezone ?? "",
    seat: initial?.seat ?? "",
    status: initial?.status ?? "scheduled",
    price: initial?.price ?? "",
    currency: initial?.currency ?? "CNY",
    distance: initial?.distance ?? "",
    ticket_number: initial?.ticket_number ?? "",
    booking_reference: initial?.booking_reference ?? "",
    purchase_credential_type: initial?.purchase_credential_type ?? "",
    purchase_credential: initial?.purchase_credential ?? "",
    notes: initial?.notes ?? "",
    trip_id: initial?.trip_id ?? "",
  });

  const { data: trips } = useQuery({
    queryKey: ["trips"],
    queryFn: () => api.listTrips(),
  });

  const [statusTouched, setStatusTouched] = useState(Boolean(initial));
  const [formError, setFormError] = useState<string | null>(null);

  const set = (key: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

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

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    if (!form.origin.trim() || !form.destination.trim()) {
      setFormError(t("transports.requiredRoute"));
      return;
    }
    const data: OtherTransportInput = {
      vehicle_type: form.vehicle_type || null,
      service_number: form.service_number || null,
      carrier: form.carrier || null,
      origin: form.origin || null,
      destination: form.destination || null,
      departure_time: fromLocalInput(form.departure_time),
      arrival_time: fromLocalInput(form.arrival_time),
      actual_departure_time: fromLocalInput(form.actual_departure_time),
      actual_arrival_time: fromLocalInput(form.actual_arrival_time),
      departure_gate: form.departure_gate || null,
      arrival_gate: form.arrival_gate || null,
      departure_timezone: form.departure_timezone || null,
      arrival_timezone: form.arrival_timezone || null,
      seat: form.seat || null,
      status: form.status,
      price: form.price || null,
      currency: form.currency || null,
      distance: form.distance || null,
      ticket_number: form.ticket_number || null,
      booking_reference: form.booking_reference || null,
      purchase_credential_type: form.purchase_credential_type || null,
      purchase_credential: form.purchase_credential || null,
      notes: form.notes || null,
      trip_id: form.trip_id || null,
    };
    void onSubmit(data);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-8">
      <Section title={t("transports.section.transport")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("transports.vehicleType")}>
            <Select
              value={form.vehicle_type}
              onChange={(e) => set("vehicle_type", e.target.value)}
            >
              <option value="">{t("flights.credentialType.none")}</option>
              <option value="bus">{t("transports.vehicleType.bus")}</option>
              <option value="ferry">{t("transports.vehicleType.ferry")}</option>
              <option value="taxi">{t("transports.vehicleType.taxi")}</option>
              <option value="rideshare">{t("transports.vehicleType.rideshare")}</option>
              <option value="car">{t("transports.vehicleType.car")}</option>
              <option value="bike">{t("transports.vehicleType.bike")}</option>
              <option value="walk">{t("transports.vehicleType.walk")}</option>
              <option value="cruise">{t("transports.vehicleType.cruise")}</option>
              <option value="other">{t("transports.vehicleType.other")}</option>
            </Select>
          </Field>
          <Field label={t("transports.serviceNumber")}>
            <Input
              value={form.service_number}
              onChange={(e) => set("service_number", e.target.value)}
              placeholder="BUS-5"
            />
          </Field>
          <Field label={t("transports.carrier")}>
            <Input
              value={form.carrier}
              onChange={(e) => set("carrier", e.target.value)}
              placeholder={t("transports.carrier")}
            />
          </Field>
          <Field label={t("transports.origin")} required>
            <Input
              value={form.origin}
              onChange={(e) => set("origin", e.target.value)}
              placeholder={t("transports.origin")}
            />
          </Field>
          <Field label={t("transports.destination")} required>
            <Input
              value={form.destination}
              onChange={(e) => set("destination", e.target.value)}
              placeholder={t("transports.destination")}
            />
          </Field>
          <Field label={t("transports.trip")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("transports.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name || `${trip.origin ?? ""} → ${trip.destination ?? ""}`}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("transports.status")}>
            <Select
              value={form.status}
              onChange={(e) => {
                setStatusTouched(true);
                set("status", e.target.value);
              }}
            >
              <option value="scheduled">{t("transports.status.scheduled")}</option>
              <option value="completed">{t("transports.status.completed")}</option>
              <option value="cancelled">{t("transports.status.cancelled")}</option>
            </Select>
          </Field>
        </div>
      </Section>

      <Section title={t("transports.section.schedule")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("transports.departureTime")}>
            <Input
              type="datetime-local"
              value={form.departure_time}
              onChange={(e) => setDepartureTime(e.target.value)}
            />
          </Field>
          <Field label={t("transports.arrivalTime")}>
            <Input
              type="datetime-local"
              value={form.arrival_time}
              onChange={(e) => set("arrival_time", e.target.value)}
            />
          </Field>
          <Field label={t("transports.actualDepartureTime")}>
            <Input
              type="datetime-local"
              value={form.actual_departure_time}
              onChange={(e) => set("actual_departure_time", e.target.value)}
            />
          </Field>
          <Field label={t("transports.actualArrivalTime")}>
            <Input
              type="datetime-local"
              value={form.actual_arrival_time}
              onChange={(e) => set("actual_arrival_time", e.target.value)}
            />
          </Field>
          <Field label={t("transports.departureStation")}>
            <Input
              value={form.departure_gate}
              onChange={(e) => set("departure_gate", e.target.value)}
              placeholder="A2"
            />
          </Field>
          <Field label={t("transports.arrivalStation")}>
            <Input
              value={form.arrival_gate}
              onChange={(e) => set("arrival_gate", e.target.value)}
              placeholder="C5"
            />
          </Field>
          <Field label={t("transports.departureTimezone")}>
            <Input
              value={form.departure_timezone}
              onChange={(e) => set("departure_timezone", e.target.value)}
              placeholder="Asia/Shanghai"
            />
          </Field>
          <Field label={t("transports.arrivalTimezone")}>
            <Input
              value={form.arrival_timezone}
              onChange={(e) => set("arrival_timezone", e.target.value)}
              placeholder="Asia/Shanghai"
            />
          </Field>
        </div>
      </Section>

      <Section title={t("transports.section.ticket")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("transports.seat")}>
            <Input
              value={form.seat}
              onChange={(e) => set("seat", e.target.value)}
              placeholder="12A"
            />
          </Field>
          <Field label={t("transports.price")}>
            <Input
              type="number"
              step="0.01"
              value={form.price}
              onChange={(e) => set("price", e.target.value)}
            />
          </Field>
          <Field label={t("transports.currency")}>
            <Input
              value={form.currency}
              maxLength={3}
              onChange={(e) => set("currency", e.target.value.toUpperCase())}
            />
          </Field>
          <Field label={t("transports.distance")}>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.distance}
              onChange={(e) => set("distance", e.target.value)}
            />
          </Field>
          <Field label={t("transports.ticketNumber")}>
            <Input
              value={form.ticket_number}
              onChange={(e) => set("ticket_number", e.target.value)}
              placeholder="T123456"
            />
          </Field>
          <Field label={t("transports.purchaseCredentialType")}>
            <Select
              value={form.purchase_credential_type}
              onChange={(e) => set("purchase_credential_type", e.target.value)}
            >
              <option value="">{t("flights.credentialType.none")}</option>
              <option value="id_card">{t("flights.credentialType.id_card")}</option>
              <option value="passport">{t("flights.credentialType.passport")}</option>
              <option value="hk_macau_permit">
                {t("flights.credentialType.hk_macau_permit")}
              </option>
              <option value="taiwan_permit">
                {t("flights.credentialType.taiwan_permit")}
              </option>
              <option value="other">{t("flights.credentialType.other")}</option>
            </Select>
          </Field>
          <Field label={t("transports.purchaseCredential")}>
            <Input
              value={form.purchase_credential}
              onChange={(e) => set("purchase_credential", e.target.value)}
              placeholder="123456789012345678"
            />
          </Field>
          <Field label={t("transports.bookingReference")} className="md:col-span-2">
            <Input
              value={form.booking_reference}
              onChange={(e) => set("booking_reference", e.target.value)}
              placeholder="ABCDEF"
            />
          </Field>
        </div>
      </Section>

      <Section title={t("transports.section.notes")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("transports.notes")} className="md:col-span-2">
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
        </div>
      </Section>
    </form>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {title}
      </h2>
      {children}
    </section>
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