"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

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
import type { Train, TrainInput } from "@/lib/types";

function autoStatus(departure: string, tz: string): string | null {
  if (!departure) return null;
  const iso = fromZonedInput(departure, tz);
  if (!iso) return null;
  return new Date(iso).getTime() < Date.now() ? "completed" : "scheduled";
}

type TrainFormState = {
  service_number: string;
  carrier: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  actual_departure_time: string;
  actual_arrival_time: string;
  train_type: string;
  carriage: string;
  cabin_class: string;
  seat: string;
  seat_type: string;
  ticket_type: string;
  departure_gate: string;
  arrival_gate: string;
  departure_timezone: string;
  arrival_timezone: string;
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
function snapshot(initial?: Train): TrainFormState {
  return {
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
  };
}

const FIELD_LABELS: Record<keyof TrainFormState, TranslationKey> = {
  service_number: "trains.serviceNumber",
  carrier: "trains.carrier",
  origin: "trains.origin",
  destination: "trains.destination",
  departure_time: "trains.departureTime",
  arrival_time: "trains.arrivalTime",
  actual_departure_time: "trains.actualDepartureTime",
  actual_arrival_time: "trains.actualArrivalTime",
  train_type: "trains.trainType",
  carriage: "trains.carriage",
  cabin_class: "trains.cabinClass",
  seat: "trains.seat",
  seat_type: "trains.seatType",
  ticket_type: "trains.ticketType",
  departure_gate: "trains.departurePlatform",
  arrival_gate: "trains.arrivalPlatform",
  departure_timezone: "trains.departureTimezone",
  arrival_timezone: "trains.arrivalTimezone",
  status: "trains.status",
  price: "trains.price",
  currency: "trains.currency",
  distance: "trains.distance",
  ticket_number: "trains.ticketNumber",
  booking_reference: "trains.bookingReference",
  purchase_credential_type: "trains.purchaseCredentialType",
  purchase_credential: "trains.purchaseCredential",
  notes: "trains.notes",
  trip_id: "trains.trip",
};

interface TrainFormProps {
  initial?: Train;
  submitting?: boolean;
  onCancel?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSubmit: (data: TrainInput) => void | Promise<void>;
}

export function TrainForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
  onDirtyChange,
}: TrainFormProps) {
  const { user } = useAuth();
  const { t, locale } = useI18n();
  const [form, setForm] = useState<TrainFormState>(() => {
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

  const [openingForm] = useState(form);
  const dirty = JSON.stringify(form) !== JSON.stringify(openingForm);
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (!dirty || submitting) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const beforeLink = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (
        !(link instanceof HTMLAnchorElement) ||
        link.target === "_blank" ||
        link.hasAttribute("download")
      )
        return;
      if (
        link.origin !== window.location.origin ||
        link.href === window.location.href ||
        link.getAttribute("href")?.startsWith("#")
      )
        return;
      if (!window.confirm(t("common.unsaved"))) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", beforeLink, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", beforeLink, true);
    };
  }, [dirty, submitting, t]);

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
  const isChanged = (key: keyof TrainFormState) => editing && changed.has(key);

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
      setFormError(t("trains.requiredRoute"));
      return;
    }
    const data: TrainInput = {
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
          <Field label={t("trains.serviceNumber")} marked={isChanged("service_number")}>
            <Input
              value={form.service_number}
              onChange={(e) => set("service_number", e.target.value)}
              placeholder="G1"
              className="flex-1"
            />
          </Field>
          <Field label={t("trains.carrier")} marked={isChanged("carrier")}>
            <Input
              value={form.carrier}
              onChange={(e) => set("carrier", e.target.value)}
              placeholder={t("trains.carrier")}
            />
          </Field>
          <Field label={t("trains.origin")} required marked={isChanged("origin")}>
            <Input
              value={form.origin}
              onChange={(e) => set("origin", e.target.value)}
              placeholder={t("trains.origin")}
            />
          </Field>
          <Field label={t("trains.destination")} required marked={isChanged("destination")}>
            <Input
              value={form.destination}
              onChange={(e) => set("destination", e.target.value)}
              placeholder={t("trains.destination")}
            />
          </Field>
          <Field label={t("trains.trainType")} marked={isChanged("train_type")}>
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
          <Field label={t("trains.trip")} marked={isChanged("trip_id")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("trains.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name || `${trip.origin ?? ""} → ${trip.destination ?? ""}`}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("trains.status")} marked={isChanged("status")}>
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
          <Field label={t("trains.departureTime")} marked={isChanged("departure_time")}>
            <DateTimeLocalInput
              value={form.departure_time}
              onChange={(e) => setDepartureTime(e.target.value)}
            />
          </Field>
          <Field label={t("trains.arrivalTime")} marked={isChanged("arrival_time")}>
            <DateTimeLocalInput
              value={form.arrival_time}
              onChange={(e) => set("arrival_time", e.target.value)}
            />
          </Field>
          <Field label={t("trains.actualDepartureTime")} marked={isChanged("actual_departure_time")}>
            <DateTimeLocalInput
              value={form.actual_departure_time}
              onChange={(e) => set("actual_departure_time", e.target.value)}
            />
          </Field>
          <Field label={t("trains.actualArrivalTime")} marked={isChanged("actual_arrival_time")}>
            <DateTimeLocalInput
              value={form.actual_arrival_time}
              onChange={(e) => set("actual_arrival_time", e.target.value)}
            />
          </Field>
          <Field label={t("trains.departureTimezone")} marked={isChanged("departure_timezone")}>
            <TimezoneSelect
              value={form.departure_timezone}
              onChange={(value) => set("departure_timezone", value)}
            />
          </Field>
          <Field label={t("trains.arrivalTimezone")} marked={isChanged("arrival_timezone")}>
            <TimezoneSelect
              value={form.arrival_timezone}
              onChange={(value) => set("arrival_timezone", value)}
            />
          </Field>
        </div>
      </Section>

      <Section title={t("trains.section.platform")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("trains.departurePlatform")} marked={isChanged("departure_gate")}>
            <Input
              value={form.departure_gate}
              onChange={(e) => set("departure_gate", e.target.value)}
              placeholder="12"
            />
          </Field>
          <Field label={t("trains.arrivalPlatform")} marked={isChanged("arrival_gate")}>
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
          <Field label={t("trains.cabinClass")} marked={isChanged("cabin_class")}>
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
          <Field label={t("trains.carriage")} marked={isChanged("carriage")}>
            <Input
              value={form.carriage}
              onChange={(e) => set("carriage", e.target.value)}
              placeholder="08"
            />
          </Field>
          <Field label={t("trains.seat")} marked={isChanged("seat")}>
            <Input
              value={form.seat}
              onChange={(e) => set("seat", e.target.value)}
              placeholder="12A"
            />
          </Field>
          <Field label={t("trains.seatType")} marked={isChanged("seat_type")}>
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
          <Field label={t("trains.ticketType")} marked={isChanged("ticket_type")}>
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
          <Field label={t("trains.price")} marked={isChanged("price")}>
            <Input
              type="number"
              step="0.01"
              value={form.price}
              onChange={(e) => set("price", e.target.value)}
            />
          </Field>
          <Field label={t("trains.currency")} marked={isChanged("currency")}>
            <Input
              value={form.currency}
              maxLength={3}
              onChange={(e) => set("currency", e.target.value.toUpperCase())}
            />
          </Field>
          <Field label={t("trains.distance")} marked={isChanged("distance")}>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.distance}
              onChange={(e) => set("distance", e.target.value)}
            />
          </Field>
          <Field label={t("trains.ticketNumber")} marked={isChanged("ticket_number")}>
            <Input
              value={form.ticket_number}
              onChange={(e) => set("ticket_number", e.target.value)}
              placeholder="E123456789"
            />
          </Field>
          <Field label={t("trains.purchaseCredentialType")} marked={isChanged("purchase_credential_type")}>
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
          <Field label={t("trains.purchaseCredential")} marked={isChanged("purchase_credential")}>
            <Input
              value={form.purchase_credential}
              onChange={(e) => set("purchase_credential", e.target.value)}
              placeholder="123456789012345678"
            />
          </Field>
          <Field
            label={t("trains.bookingReference")}
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

      <Section title={t("trains.section.notes")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field
            label={t("trains.notes")}
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
                      ? t("trains.changedOne")
                      : t("trains.changedMany", { count: changed.size })}
                  </Badge>
                  <span className="text-sm text-foreground/80">
                    {changedLabels.join(joiner)}
                  </span>
                </div>
              ) : (
                <p className="px-0.5 text-sm text-muted-foreground">
                  {t("trains.noChanges")}
                </p>
              )}
            </div>
          ) : null}
          <div className="flex items-center gap-3 md:col-span-2">
            <Button type="submit" disabled={submitting}>
              {t("common.save")}
            </Button>
            {onCancel ? (
              <Button type="button" variant="outline" disabled={submitting} onClick={onCancel}>
                {t("common.cancel")}
              </Button>
            ) : null}
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
            {t("trains.changedMarker")}
          </span>
        ) : null}
      </Label>
      {children}
    </div>
  );
}
