"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DateInput } from "@/components/ui/date-input";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Hotel, HotelInput, TripList } from "@/lib/types";

interface HotelFormProps {
  initial?: Hotel;
  submitting?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onCancel?: () => void;
  onSubmit: (input: HotelInput) => void;
}

interface FormState {
  hotel: string;
  check_in: string;
  check_out: string;
  status: string;
  room_type: string;
  room_number: string;
  booking_reference: string;
  price: string;
  currency: string;
  address: string;
  notes: string;
  trip_id: string;
  lat: string;
  lon: string;
}

function toForm(hotel?: Hotel): FormState {
  return {
    hotel: hotel?.hotel ?? "",
    check_in: hotel?.check_in ?? "",
    check_out: hotel?.check_out ?? "",
    status: hotel?.status ?? "scheduled",
    room_type: hotel?.room_type ?? "",
    room_number: hotel?.room_number ?? "",
    booking_reference: hotel?.booking_reference ?? "",
    price: hotel?.price != null ? String(hotel.price) : "",
    currency: hotel?.currency ?? "",
    address: hotel?.address ?? "",
    notes: hotel?.notes ?? "",
    trip_id: hotel?.trip_id ?? "",
    lat: hotel?.lat != null ? String(hotel.lat) : "",
    lon: hotel?.lon != null ? String(hotel.lon) : "",
  };
}

function toInput(form: FormState): HotelInput {
  // Coordinates are optional: only send them when both are filled, otherwise
  // an edit would silently wipe a pin placed by the locate action.
  const lat = form.lat.trim() === "" ? null : Number(form.lat);
  const lon = form.lon.trim() === "" ? null : Number(form.lon);
  const coordinates =
    lat !== null && lon !== null && Number.isFinite(lat) && Number.isFinite(lon)
      ? { lat, lon }
      : {};
  return {
    hotel: form.hotel.trim() || undefined,
    check_in: form.check_in || undefined,
    check_out: form.check_out || null,
    status: form.status,
    room_type: form.room_type || null,
    room_number: form.room_number || null,
    booking_reference: form.booking_reference || null,
    price: form.price ? Number(form.price) : null,
    currency: form.currency.toUpperCase() || null,
    address: form.address || null,
    notes: form.notes || null,
    trip_id: form.trip_id || null,
    ...coordinates,
  };
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

export function HotelForm({
  initial,
  submitting,
  onDirtyChange,
  onCancel,
  onSubmit,
}: HotelFormProps) {
  const { t } = useI18n();
  const [form, setForm] = useState<FormState>(() => toForm(initial));
  const { data: trips } = useQuery<TripList>({
    queryKey: ["trips", { page_size: 100 }],
    queryFn: () => api.listTrips({ page_size: 100 }),
  });

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    onDirtyChange?.(true);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(toInput(form));
  };

  return (
    <form onSubmit={submit}>
      <Card>
        <CardContent className="grid gap-4 p-5 sm:grid-cols-2">
          <Field label={t("hotels.name")}>
            <Input
              required
              value={form.hotel}
              maxLength={160}
              onChange={(e) => set("hotel", e.target.value)}
            />
          </Field>
          <Field label={t("hotels.trip")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("hotels.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("hotels.checkIn")}>
            <DateInput
              required
              value={form.check_in}
              onChange={(e) => set("check_in", e.target.value)}
            />
          </Field>
          <Field label={t("hotels.checkOut")}>
            <DateInput
              value={form.check_out}
              onChange={(e) => set("check_out", e.target.value)}
            />
          </Field>
          <Field label={t("hotels.status")}>
            <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
              <option value="scheduled">{t("hotels.status.scheduled")}</option>
              <option value="completed">{t("hotels.status.completed")}</option>
              <option value="cancelled">{t("hotels.status.cancelled")}</option>
            </Select>
          </Field>
          <Field label={t("hotels.roomType")}>
            <Input value={form.room_type} maxLength={60} onChange={(e) => set("room_type", e.target.value)} />
          </Field>
          <Field label={t("hotels.roomNumber")}>
            <Input value={form.room_number} maxLength={20} onChange={(e) => set("room_number", e.target.value)} />
          </Field>
          <Field label={t("hotels.bookingRef")}>
            <Input
              value={form.booking_reference}
              maxLength={64}
              onChange={(e) => set("booking_reference", e.target.value)}
            />
          </Field>
          <Field label={t("hotels.price")}>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.price}
              onChange={(e) => set("price", e.target.value)}
            />
          </Field>
          <Field label={t("hotels.currency")}>
            <Input
              value={form.currency}
              maxLength={3}
              onChange={(e) => set("currency", e.target.value.toUpperCase())}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label={t("hotels.address")}>
              <Input value={form.address} maxLength={300} onChange={(e) => set("address", e.target.value)} />
            </Field>
          </div>
          <div className="grid gap-4 sm:col-span-2 sm:grid-cols-2">
            <Field label={t("hotels.lat")}>
              <Input
                type="number"
                step="any"
                min={-90}
                max={90}
                value={form.lat}
                placeholder="31.2304"
                onChange={(e) => set("lat", e.target.value)}
              />
            </Field>
            <Field label={t("hotels.lon")}>
              <Input
                type="number"
                step="any"
                min={-180}
                max={180}
                value={form.lon}
                placeholder="121.4737"
                onChange={(e) => set("lon", e.target.value)}
              />
            </Field>
            <p className="text-xs text-muted-foreground sm:col-span-2">
              {t("hotels.coordinatesHint")}
            </p>
          </div>
          <div className="sm:col-span-2">
            <Field label={t("hotels.notes")}>
              <Textarea rows={3} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
            </Field>
          </div>
        </CardContent>
      </Card>
      <div className="mt-4 flex justify-end gap-3">
        {onCancel ? (
          <Button type="button" variant="outline" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
        ) : null}
        <Button type="submit" disabled={submitting}>
          {submitting ? t("common.loading") : t("common.save")}
        </Button>
      </div>
    </form>
  );
}