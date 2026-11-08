"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CurrencySelect } from "@/components/ui/currency-select";
import { DateTimeLocalInput } from "@/components/ui/date-input";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { fromZonedInput, toLocalInput } from "@/lib/datetime";
import { useI18n } from "@/lib/i18n";
import type {
  Activity,
  ActivityInput,
  ActivityType,
  PlaceList,
  TripList,
} from "@/lib/types";

const TYPES: ActivityType[] = [
  "sightseeing",
  "theme_park",
  "museum",
  "culture",
  "outdoor",
  "sports",
  "dining",
  "shopping",
  "entertainment",
  "event",
  "experience",
  "wellness",
  "visit",
  "other",
];

interface ActivityFormProps {
  initial?: Activity;
  submitting?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onCancel?: () => void;
  onSubmit: (input: ActivityInput) => void;
}

interface FormState {
  name: string;
  type: ActivityType;
  trip_id: string;
  place_id: string;
  start_at: string;
  end_at: string;
  price: string;
  currency: string;
  notes: string;
}

function toForm(activity?: Activity): FormState {
  return {
    name: activity?.name ?? "",
    type: activity?.type ?? "sightseeing",
    trip_id: activity?.trip_id ?? "",
    place_id: activity?.place_id ?? "",
    start_at: toLocalInput(activity?.start_at),
    end_at: toLocalInput(activity?.end_at),
    price: activity?.price ?? "",
    currency: activity?.currency ?? "",
    notes: activity?.notes ?? "",
  };
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function toInput(form: FormState): ActivityInput {
  return {
    name: form.name.trim(),
    type: form.type,
    trip_id: form.trip_id || null,
    place_id: form.place_id || null,
    start_at: fromZonedInput(form.start_at),
    end_at: fromZonedInput(form.end_at),
    price: optionalNumber(form.price),
    currency: form.currency.trim().toUpperCase() || null,
    notes: form.notes.trim() || null,
  };
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

export function ActivityForm({
  initial,
  submitting,
  onDirtyChange,
  onCancel,
  onSubmit,
}: ActivityFormProps) {
  const { t } = useI18n();
  const [form, setForm] = useState<FormState>(() => toForm(initial));
  const [windowError, setWindowError] = useState(false);
  const { data: trips } = useQuery<TripList>({
    queryKey: ["trips", { page_size: 100 }],
    queryFn: () => api.listTrips({ page_size: 100 }),
  });
  const { data: places } = useQuery<PlaceList>({
    queryKey: ["places", { page_size: 100 }],
    queryFn: () => api.listPlaces({ page_size: 100 }),
  });

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    onDirtyChange?.(true);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (form.start_at && form.end_at && form.end_at < form.start_at) {
      setWindowError(true);
      return;
    }
    setWindowError(false);
    onSubmit(toInput(form));
  };

  return (
    <form onSubmit={submit}>
      <Card>
        <CardContent className="grid gap-4 p-5 sm:grid-cols-2">
          <Field label={t("activities.name")}>
            <Input
              required
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
            />
          </Field>
          <Field label={t("activities.type")}>
            <Select
              value={form.type}
              onChange={(e) => set("type", e.target.value as ActivityType)}
            >
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`activities.type.${type}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("activities.trip")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("activities.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("activities.place")}>
            <Select value={form.place_id} onChange={(e) => set("place_id", e.target.value)}>
              <option value="">{t("activities.placeNone")}</option>
              {places?.items.map((place) => (
                <option key={place.id} value={place.id}>
                  {place.name}
                  {place.city ? ` · ${place.city}` : ""}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("activities.startAt")}>
            <DateTimeLocalInput
              value={form.start_at}
              onChange={(e) => set("start_at", e.target.value)}
            />
          </Field>
          <Field label={t("activities.endAt")}>
            <DateTimeLocalInput
              value={form.end_at}
              onChange={(e) => set("end_at", e.target.value)}
            />
          </Field>
          <Field label={t("activities.price")}>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.price}
              onChange={(e) => set("price", e.target.value)}
            />
          </Field>
          <Field label={t("activities.currency")}>
            <CurrencySelect
              value={form.currency}
              onChange={(value) => set("currency", value)}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label={t("activities.notes")}>
              <Textarea
                rows={3}
                value={form.notes}
                onChange={(e) => set("notes", e.target.value)}
              />
            </Field>
          </div>
          {windowError ? (
            <p role="alert" className="text-xs text-danger sm:col-span-2">
              {t("activities.windowInvalid")}
            </p>
          ) : null}
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
