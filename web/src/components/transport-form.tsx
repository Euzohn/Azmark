"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DateTimeLocalInput } from "@/components/ui/date-input";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { TimezoneSelect } from "@/components/ui/timezone-select";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { fromZonedInput, toZonedInput } from "@/lib/datetime";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { defaultTimezone } from "@/lib/timezones";
import { useFormDiff } from "@/lib/use-form-diff";
import { cn } from "@/lib/utils";
import type { OtherTransport, OtherTransportInput } from "@/lib/types";

function autoStatus(departure: string, tz: string): string | null {
  if (!departure) return null;
  const iso = fromZonedInput(departure, tz);
  if (!iso) return null;
  return new Date(iso).getTime() < Date.now() ? "completed" : "scheduled";
}

type TransportFormState = {
  vehicle_type: string;
  service_number: string;
  carrier: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  actual_departure_time: string;
  actual_arrival_time: string;
  departure_gate: string;
  arrival_gate: string;
  departure_timezone: string;
  arrival_timezone: string;
  seat: string;
  status: string;
  price: string;
  currency: string;
  distance: string;
  ticket_number: string;
  booking_reference: string;
  purchase_credential_type: string;
  purchase_credential: string;
  notes: string;
  trip_id: string;
};

/** The value each field would hold if untouched: the saved record, or blank. */
function snapshot(initial?: OtherTransport): TransportFormState {
  return {
    vehicle_type: initial?.vehicle_type ?? "",
    service_number: initial?.service_number ?? "",
    carrier: initial?.carrier ?? "",
    origin: initial?.origin ?? "",
    destination: initial?.destination ?? "",
    departure_time: toZonedInput(initial?.departure_time, initial?.departure_timezone),
    arrival_time: toZonedInput(initial?.arrival_time, initial?.arrival_timezone),
    actual_departure_time: toZonedInput(
      initial?.actual_departure_time,
      initial?.departure_timezone,
    ),
    actual_arrival_time: toZonedInput(
      initial?.actual_arrival_time,
      initial?.arrival_timezone,
    ),
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
  };
}

const FIELD_LABELS: Record<keyof TransportFormState, TranslationKey> = {
  vehicle_type: "transports.vehicleType",
  service_number: "transports.serviceNumber",
  carrier: "transports.carrier",
  origin: "transports.origin",
  destination: "transports.destination",
  departure_time: "transports.departureTime",
  arrival_time: "transports.arrivalTime",
  actual_departure_time: "transports.actualDepartureTime",
  actual_arrival_time: "transports.actualArrivalTime",
  departure_gate: "transports.departureStation",
  arrival_gate: "transports.arrivalStation",
  departure_timezone: "transports.departureTimezone",
  arrival_timezone: "transports.arrivalTimezone",
  seat: "transports.seat",
  status: "transports.status",
  price: "transports.price",
  currency: "transports.currency",
  distance: "transports.distance",
  ticket_number: "transports.ticketNumber",
  booking_reference: "transports.bookingReference",
  purchase_credential_type: "transports.purchaseCredentialType",
  purchase_credential: "transports.purchaseCredential",
  notes: "transports.notes",
  trip_id: "transports.trip",
};

interface TransportFormProps {
  initial?: OtherTransport;
  submitting?: boolean;
  onSubmit: (data: OtherTransportInput) => void | Promise<void>;
}

export function TransportForm({ initial, submitting, onSubmit }: TransportFormProps) {
  const { user } = useAuth();
  const { t, locale } = useI18n();
  const [form, setForm] = useState<TransportFormState>(() => {
    const base = snapshot(initial);
    if (initial) return base;
    // New records start in the traveller's own zone (profile setting).
    const tz = defaultTimezone(user?.timezone);
    return {
      ...base,
      departure_timezone: base.departure_timezone || tz,
      arrival_timezone: base.arrival_timezone || tz,
    };
  });

  const { data: trips } = useQuery({
    queryKey: ["trips"],
    queryFn: () => api.listTrips(),
  });

  const [statusTouched, setStatusTouched] = useState(Boolean(initial));
  const [formError, setFormError] = useState<string | null>(null);

  const set = (key: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const editing = Boolean(initial);
  const baseline = useMemo(() => snapshot(initial), [initial]);
  const { changed, changedLabels } = useFormDiff(form, baseline, FIELD_LABELS);
  const joiner = locale === "zh-CN" ? "、" : ", ";
  // Mark only when editing — a blank record is not "modified".
  const isChanged = (key: keyof TransportFormState) => editing && changed.has(key);

  const setDepartureTime = (value: string) => {
    setForm((prev) => {
      const next = { ...prev, departure_time: value };
      if (!statusTouched) {
        const status = autoStatus(value, prev.departure_timezone);
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
      departure_time: fromZonedInput(form.departure_time, form.departure_timezone),
      arrival_time: fromZonedInput(form.arrival_time, form.arrival_timezone),
      actual_departure_time: fromZonedInput(
        form.actual_departure_time,
        form.departure_timezone,
      ),
      actual_arrival_time: fromZonedInput(
        form.actual_arrival_time,
        form.arrival_timezone,
      ),
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
          <Field label={t("transports.vehicleType")} marked={isChanged("vehicle_type")}>
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
          <Field label={t("transports.serviceNumber")} marked={isChanged("service_number")}>
            <Input
              value={form.service_number}
              onChange={(e) => set("service_number", e.target.value)}
              placeholder="BUS-5"
            />
          </Field>
          <Field label={t("transports.carrier")} marked={isChanged("carrier")}>
            <Input
              value={form.carrier}
              onChange={(e) => set("carrier", e.target.value)}
              placeholder={t("transports.carrier")}
            />
          </Field>
          <Field label={t("transports.origin")} required marked={isChanged("origin")}>
            <Input
              value={form.origin}
              onChange={(e) => set("origin", e.target.value)}
              placeholder={t("transports.origin")}
            />
          </Field>
          <Field label={t("transports.destination")} required marked={isChanged("destination")}>
            <Input
              value={form.destination}
              onChange={(e) => set("destination", e.target.value)}
              placeholder={t("transports.destination")}
            />
          </Field>
          <Field label={t("transports.trip")} marked={isChanged("trip_id")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("transports.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name || `${trip.origin ?? ""} → ${trip.destination ?? ""}`}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("transports.status")} marked={isChanged("status")}>
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
          <Field label={t("transports.departureTime")} marked={isChanged("departure_time")}>
            <DateTimeLocalInput
              value={form.departure_time}
              onChange={(e) => setDepartureTime(e.target.value)}
            />
          </Field>
          <Field label={t("transports.arrivalTime")} marked={isChanged("arrival_time")}>
            <DateTimeLocalInput
              value={form.arrival_time}
              onChange={(e) => set("arrival_time", e.target.value)}
            />
          </Field>
          <Field label={t("transports.actualDepartureTime")} marked={isChanged("actual_departure_time")}>
            <DateTimeLocalInput
              value={form.actual_departure_time}
              onChange={(e) => set("actual_departure_time", e.target.value)}
            />
          </Field>
          <Field label={t("transports.actualArrivalTime")} marked={isChanged("actual_arrival_time")}>
            <DateTimeLocalInput
              value={form.actual_arrival_time}
              onChange={(e) => set("actual_arrival_time", e.target.value)}
            />
          </Field>
          <Field label={t("transports.departureStation")} marked={isChanged("departure_gate")}>
            <Input
              value={form.departure_gate}
              onChange={(e) => set("departure_gate", e.target.value)}
              placeholder="A2"
            />
          </Field>
          <Field label={t("transports.arrivalStation")} marked={isChanged("arrival_gate")}>
            <Input
              value={form.arrival_gate}
              onChange={(e) => set("arrival_gate", e.target.value)}
              placeholder="C5"
            />
          </Field>
          <Field
            label={t("transports.departureTimezone")}
            marked={isChanged("departure_timezone")}
          >
            <TimezoneSelect
              value={form.departure_timezone}
              onChange={(value) => set("departure_timezone", value)}
            />
          </Field>
          <Field
            label={t("transports.arrivalTimezone")}
            marked={isChanged("arrival_timezone")}
          >
            <TimezoneSelect
              value={form.arrival_timezone}
              onChange={(value) => set("arrival_timezone", value)}
            />
          </Field>
        </div>
      </Section>

      <Section title={t("transports.section.ticket")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("transports.seat")} marked={isChanged("seat")}>
            <Input
              value={form.seat}
              onChange={(e) => set("seat", e.target.value)}
              placeholder="12A"
            />
          </Field>
          <Field label={t("transports.price")} marked={isChanged("price")}>
            <Input
              type="number"
              step="0.01"
              value={form.price}
              onChange={(e) => set("price", e.target.value)}
            />
          </Field>
          <Field label={t("transports.currency")} marked={isChanged("currency")}>
            <Input
              value={form.currency}
              maxLength={3}
              onChange={(e) => set("currency", e.target.value.toUpperCase())}
            />
          </Field>
          <Field label={t("transports.distance")} marked={isChanged("distance")}>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.distance}
              onChange={(e) => set("distance", e.target.value)}
            />
          </Field>
          <Field label={t("transports.ticketNumber")} marked={isChanged("ticket_number")}>
            <Input
              value={form.ticket_number}
              onChange={(e) => set("ticket_number", e.target.value)}
              placeholder="T123456"
            />
          </Field>
          <Field label={t("transports.purchaseCredentialType")} marked={isChanged("purchase_credential_type")}>
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
          <Field label={t("transports.purchaseCredential")} marked={isChanged("purchase_credential")}>
            <Input
              value={form.purchase_credential}
              onChange={(e) => set("purchase_credential", e.target.value)}
              placeholder="123456789012345678"
            />
          </Field>
          <Field
            label={t("transports.bookingReference")}
            marked={isChanged("booking_reference")}
            className="md:col-span-2"
          >
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
          <Field
            label={t("transports.notes")}
            marked={isChanged("notes")}
            className="md:col-span-2"
          >
            <Textarea
              rows={3}
              value={form.notes}
              onChange={(e) => set("notes", e.target.value)}
            />
          </Field>
          {editing ? (
            <div className="md:col-span-2">
              {changed.size > 0 ? (
                <div className="flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-3.5 py-2.5">
                  <Badge variant="primary">
                    {changed.size === 1
                      ? t("transports.changedOne")
                      : t("transports.changedMany", { count: changed.size })}
                  </Badge>
                  <span className="text-sm text-foreground/80">
                    {changedLabels.join(joiner)}
                  </span>
                </div>
              ) : (
                <p className="px-0.5 text-sm text-muted-foreground">
                  {t("transports.noChanges")}
                </p>
              )}
            </div>
          ) : null}
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
  marked,
  className,
  children,
}: {
  label: string;
  required?: boolean;
  marked?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className={cn(className, marked && "field-changed")}>
      <Label className="mb-1.5 flex items-center gap-2">
        <span>
          {label}
          {required ? (
            <span className="text-danger" aria-hidden="true">
              *
            </span>
          ) : null}
        </span>
        {marked ? (
          <span className="inline-flex items-center rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-primary">
            {t("transports.changedMarker")}
          </span>
        ) : null}
      </Label>
      {children}
    </div>
  );
}