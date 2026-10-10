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
import type { Train, TrainInput } from "@/lib/types";

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

interface TrainFormProps {
  initial?: Train;
  submitting?: boolean;
  onSubmit: (data: TrainInput) => void | Promise<void>;
}

export function TrainForm({ initial, submitting, onSubmit }: TrainFormProps) {
  const { t } = useI18n();
  const [form, setForm] = useState({
    service_number: initial?.service_number ?? "",
    carrier: initial?.carrier ?? "",
    origin: initial?.origin ?? "",
    destination: initial?.destination ?? "",
    departure_time: toLocalInput(initial?.departure_time),
    arrival_time: toLocalInput(initial?.arrival_time),
    actual_departure_time: toLocalInput(initial?.actual_departure_time),
    actual_arrival_time: toLocalInput(initial?.actual_arrival_time),
    train_type: initial?.train_type ?? "",
    carriage: initial?.carriage ?? "",
    cabin_class: initial?.cabin_class ?? "",
    seat: initial?.seat ?? "",
    seat_type: initial?.seat_type ?? "",
    ticket_type: initial?.ticket_type ?? "",
    departure_gate: initial?.departure_gate ?? "",
    arrival_gate: initial?.arrival_gate ?? "",
    departure_timezone: initial?.departure_timezone ?? "",
    arrival_timezone: initial?.arrival_timezone ?? "",
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
      setFormError(t("trains.requiredRoute"));
      return;
    }
    const data: TrainInput = {
      service_number: form.service_number || null,
      carrier: form.carrier || null,
      origin: form.origin || null,
      destination: form.destination || null,
      departure_time: fromLocalInput(form.departure_time),
      arrival_time: fromLocalInput(form.arrival_time),
      actual_departure_time: fromLocalInput(form.actual_departure_time),
      actual_arrival_time: fromLocalInput(form.actual_arrival_time),
      train_type: form.train_type || null,
      carriage: form.carriage || null,
      cabin_class: form.cabin_class || null,
      seat: form.seat || null,
      seat_type: form.seat_type || null,
      ticket_type: form.ticket_type || null,
      departure_gate: form.departure_gate || null,
      arrival_gate: form.arrival_gate || null,
      departure_timezone: form.departure_timezone || null,
      arrival_timezone: form.arrival_timezone || null,
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
      <Section title={t("trains.section.train")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("trains.serviceNumber")}>
            <Input
              value={form.service_number}
              onChange={(e) => set("service_number", e.target.value)}
              placeholder="G1"
              className="flex-1"
            />
          </Field>
          <Field label={t("trains.carrier")}>
            <Input
              value={form.carrier}
              onChange={(e) => set("carrier", e.target.value)}
              placeholder={t("trains.carrier")}
            />
          </Field>
          <Field label={t("trains.origin")} required>
            <Input
              value={form.origin}
              onChange={(e) => set("origin", e.target.value)}
              placeholder={t("trains.origin")}
            />
          </Field>
          <Field label={t("trains.destination")} required>
            <Input
              value={form.destination}
              onChange={(e) => set("destination", e.target.value)}
              placeholder={t("trains.destination")}
            />
          </Field>
          <Field label={t("trains.trainType")}>
            <Select
              value={form.train_type}
              onChange={(e) => set("train_type", e.target.value)}
            >
              <option value="">{t("flights.credentialType.none")}</option>
              <option value="high_speed">{t("trains.trainType.high_speed")}</option>
              <option value="intercity">{t("trains.trainType.intercity")}</option>
              <option value="conventional">{t("trains.trainType.conventional")}</option>
              <option value="night">{t("trains.trainType.night")}</option>
            </Select>
          </Field>
          <Field label={t("trains.trip")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("trains.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name || `${trip.origin ?? ""} → ${trip.destination ?? ""}`}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("trains.status")}>
            <Select
              value={form.status}
              onChange={(e) => {
                setStatusTouched(true);
                set("status", e.target.value);
              }}
            >
              <option value="scheduled">{t("trains.status.scheduled")}</option>
              <option value="completed">{t("trains.status.completed")}</option>
              <option value="cancelled">{t("trains.status.cancelled")}</option>
            </Select>
          </Field>
        </div>
      </Section>

      <Section title={t("trains.section.schedule")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("trains.departureTime")}>
            <Input
              type="datetime-local"
              value={form.departure_time}
              onChange={(e) => setDepartureTime(e.target.value)}
            />
          </Field>
          <Field label={t("trains.arrivalTime")}>
            <Input
              type="datetime-local"
              value={form.arrival_time}
              onChange={(e) => set("arrival_time", e.target.value)}
            />
          </Field>
          <Field label={t("trains.actualDepartureTime")}>
            <Input
              type="datetime-local"
              value={form.actual_departure_time}
              onChange={(e) => set("actual_departure_time", e.target.value)}
            />
          </Field>
          <Field label={t("trains.actualArrivalTime")}>
            <Input
              type="datetime-local"
              value={form.actual_arrival_time}
              onChange={(e) => set("actual_arrival_time", e.target.value)}
            />
          </Field>
          <Field label={t("trains.departureTimezone")}>
            <Input
              value={form.departure_timezone}
              onChange={(e) => set("departure_timezone", e.target.value)}
              placeholder="Asia/Shanghai"
            />
          </Field>
          <Field label={t("trains.arrivalTimezone")}>
            <Input
              value={form.arrival_timezone}
              onChange={(e) => set("arrival_timezone", e.target.value)}
              placeholder="Asia/Beijing"
            />
          </Field>
        </div>
      </Section>

      <Section title={t("trains.section.platform")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("trains.departurePlatform")}>
            <Input
              value={form.departure_gate}
              onChange={(e) => set("departure_gate", e.target.value)}
              placeholder="12"
            />
          </Field>
          <Field label={t("trains.arrivalPlatform")}>
            <Input
              value={form.arrival_gate}
              onChange={(e) => set("arrival_gate", e.target.value)}
              placeholder="8"
            />
          </Field>
        </div>
      </Section>

      <Section title={t("trains.section.seat")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("trains.cabinClass")}>
            <Select
              value={form.cabin_class}
              onChange={(e) => set("cabin_class", e.target.value)}
            >
              <option value="">{t("flights.credentialType.none")}</option>
              <option value="business">{t("trains.cabin.business")}</option>
              <option value="first">{t("trains.cabin.first")}</option>
              <option value="second">{t("trains.cabin.second")}</option>
              <option value="premium_soft">{t("trains.cabin.premium_soft")}</option>
              <option value="hard">{t("trains.cabin.hard")}</option>
              <option value="hard_seat">{t("trains.cabin.hard_seat")}</option>
              <option value="soft_seat">{t("trains.cabin.soft_seat")}</option>
            </Select>
          </Field>
          <Field label={t("trains.carriage")}>
            <Input
              value={form.carriage}
              onChange={(e) => set("carriage", e.target.value)}
              placeholder="08"
            />
          </Field>
          <Field label={t("trains.seat")}>
            <Input
              value={form.seat}
              onChange={(e) => set("seat", e.target.value)}
              placeholder="12A"
            />
          </Field>
          <Field label={t("trains.seatType")}>
            <Select
              value={form.seat_type}
              onChange={(e) => set("seat_type", e.target.value)}
            >
              <option value="">{t("flights.credentialType.none")}</option>
              <option value="window">{t("trains.seatType.window")}</option>
              <option value="aisle">{t("trains.seatType.aisle")}</option>
              <option value="middle">{t("trains.seatType.middle")}</option>
              <option value="sleeper">{t("trains.seatType.sleeper")}</option>
              <option value="reclining">{t("trains.seatType.reclining")}</option>
              <option value="standing">{t("trains.seatType.standing")}</option>
            </Select>
          </Field>
          <Field label={t("trains.ticketType")}>
            <Select
              value={form.ticket_type}
              onChange={(e) => set("ticket_type", e.target.value)}
            >
              <option value="">{t("flights.credentialType.none")}</option>
              <option value="reserved">{t("trains.ticketType.reserved")}</option>
              <option value="standing">{t("trains.ticketType.standing")}</option>
              <option value="student">{t("trains.ticketType.student")}</option>
              <option value="child">{t("trains.ticketType.child")}</option>
            </Select>
          </Field>
        </div>
      </Section>

      <Section title={t("trains.section.ticket")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("trains.price")}>
            <Input
              type="number"
              step="0.01"
              value={form.price}
              onChange={(e) => set("price", e.target.value)}
            />
          </Field>
          <Field label={t("trains.currency")}>
            <Input
              value={form.currency}
              maxLength={3}
              onChange={(e) => set("currency", e.target.value.toUpperCase())}
            />
          </Field>
          <Field label={t("trains.distance")}>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.distance}
              onChange={(e) => set("distance", e.target.value)}
            />
          </Field>
          <Field label={t("trains.ticketNumber")}>
            <Input
              value={form.ticket_number}
              onChange={(e) => set("ticket_number", e.target.value)}
              placeholder="E123456789"
            />
          </Field>
          <Field label={t("trains.purchaseCredentialType")}>
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
          <Field label={t("trains.purchaseCredential")}>
            <Input
              value={form.purchase_credential}
              onChange={(e) => set("purchase_credential", e.target.value)}
              placeholder="123456789012345678"
            />
          </Field>
          <Field label={t("trains.bookingReference")} className="md:col-span-2">
            <Input
              value={form.booking_reference}
              onChange={(e) => set("booking_reference", e.target.value)}
              placeholder="ABCDEF"
            />
          </Field>
        </div>
      </Section>

      <Section title={t("trains.section.notes")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("trains.notes")} className="md:col-span-2">
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
