"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { fromZonedInput, toLocalInput } from "@/lib/datetime";
import { useI18n } from "@/lib/i18n";
import type { Photo, PhotoInput, TripList } from "@/lib/types";

interface PhotoFormProps {
  initial: Photo;
  submitting?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onCancel?: () => void;
  onSubmit: (input: PhotoInput) => void;
}

interface FormState {
  filename: string;
  captured_at: string;
  latitude: string;
  longitude: string;
  trip_id: string;
}

function toForm(photo: Photo): FormState {
  return {
    filename: photo.filename,
    // EXIF capture time is an instant; show and edit it in the browser's zone.
    captured_at: toLocalInput(photo.captured_at),
    latitude: photo.latitude === null ? "" : String(photo.latitude),
    longitude: photo.longitude === null ? "" : String(photo.longitude),
    trip_id: photo.trip_id ?? "",
  };
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function toInput(form: FormState): PhotoInput {
  return {
    filename: form.filename.trim(),
    captured_at: fromZonedInput(form.captured_at),
    latitude: numberOrNull(form.latitude),
    longitude: numberOrNull(form.longitude),
    trip_id: form.trip_id || null,
  };
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
      {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
    </label>
  );
}

/**
 * Edits the metadata that EXIF may not have provided. The binary itself is
 * immutable — re-uploading is the only way to change the image.
 */
export function PhotoForm({
  initial,
  submitting,
  onDirtyChange,
  onCancel,
  onSubmit,
}: PhotoFormProps) {
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
        <CardContent className="grid gap-4 p-5">
          <Field label={t("photos.filename")}>
            <Input
              required
              value={form.filename}
              maxLength={255}
              onChange={(e) => set("filename", e.target.value)}
            />
          </Field>
          <Field label={t("photos.capturedAt")} hint={t("photos.capturedAtHint")}>
            <Input
              type="datetime-local"
              value={form.captured_at}
              onChange={(e) => set("captured_at", e.target.value)}
            />
          </Field>
          <div className="flex flex-col gap-1.5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("photos.latitude")}>
                <Input
                  type="number"
                  inputMode="decimal"
                  step="any"
                  min={-90}
                  max={90}
                  value={form.latitude}
                  onChange={(e) => set("latitude", e.target.value)}
                />
              </Field>
              <Field label={t("photos.longitude")}>
                <Input
                  type="number"
                  inputMode="decimal"
                  step="any"
                  min={-180}
                  max={180}
                  value={form.longitude}
                  onChange={(e) => set("longitude", e.target.value)}
                />
              </Field>
            </div>
            <span className="text-xs text-muted-foreground">{t("photos.locationHint")}</span>
          </div>
          <Field label={t("photos.trip")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("photos.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name}
                </option>
              ))}
            </Select>
          </Field>
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
