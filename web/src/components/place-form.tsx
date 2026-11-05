"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { TimezoneSelect } from "@/components/ui/timezone-select";
import { useI18n } from "@/lib/i18n";
import type { Place, PlaceInput, PlaceType } from "@/lib/types";

const TYPES: PlaceType[] = [
  "airport",
  "train_station",
  "bus_station",
  "port",
  "hotel",
  "restaurant",
  "attraction",
  "city",
  "place",
  "other",
];

interface PlaceFormProps {
  initial?: Place;
  submitting?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onCancel?: () => void;
  onSubmit: (input: PlaceInput) => void;
}

interface FormState {
  type: PlaceType;
  name: string;
  localized_name: string;
  country: string;
  region: string;
  city: string;
  district: string;
  lat: string;
  lon: string;
  timezone: string;
  external_ids: string;
}

function toForm(place?: Place): FormState {
  return {
    type: place?.type ?? "place",
    name: place?.name ?? "",
    localized_name: place?.localized_name ?? "",
    country: place?.country ?? "",
    region: place?.region ?? "",
    city: place?.city ?? "",
    district: place?.district ?? "",
    lat: place?.lat != null ? String(place.lat) : "",
    lon: place?.lon != null ? String(place.lon) : "",
    timezone: place?.timezone ?? "",
    external_ids: place?.external_ids ? JSON.stringify(place.external_ids, null, 2) : "",
  };
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
      {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
    </label>
  );
}

export function PlaceForm({
  initial,
  submitting,
  onDirtyChange,
  onCancel,
  onSubmit,
}: PlaceFormProps) {
  const { t } = useI18n();
  const [form, setForm] = useState<FormState>(() => toForm(initial));
  const [jsonError, setJsonError] = useState(false);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    onDirtyChange?.(true);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();

    let externalIds: Record<string, unknown> | null = null;
    if (form.external_ids.trim()) {
      try {
        const parsed = JSON.parse(form.external_ids);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          externalIds = parsed as Record<string, unknown>;
        } else {
          setJsonError(true);
          return;
        }
      } catch {
        setJsonError(true);
        return;
      }
    }
    setJsonError(false);

    onSubmit({
      type: form.type,
      name: form.name.trim(),
      localized_name: form.localized_name.trim() || null,
      country: form.country.trim() || null,
      region: form.region.trim() || null,
      city: form.city.trim() || null,
      district: form.district.trim() || null,
      lat: optionalNumber(form.lat),
      lon: optionalNumber(form.lon),
      timezone: form.timezone || null,
      external_ids: externalIds,
    });
  };

  return (
    <form onSubmit={submit}>
      <Card>
        <CardContent className="grid gap-4 p-5 sm:grid-cols-2">
          <Field label={t("places.name")}>
            <Input
              required
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
            />
          </Field>
          <Field label={t("places.localizedName")}>
            <Input
              value={form.localized_name}
              onChange={(e) => set("localized_name", e.target.value)}
            />
          </Field>
          <Field label={t("places.type")}>
            <Select
              value={form.type}
              onChange={(e) => set("type", e.target.value as PlaceType)}
            >
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`places.type.${type}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("places.timezone")}>
            <TimezoneSelect
              value={form.timezone}
              onChange={(value) => set("timezone", value)}
            />
          </Field>
          <Field label={t("places.country")}>
            <Input value={form.country} onChange={(e) => set("country", e.target.value)} />
          </Field>
          <Field label={t("places.region")}>
            <Input value={form.region} onChange={(e) => set("region", e.target.value)} />
          </Field>
          <Field label={t("places.city")}>
            <Input value={form.city} onChange={(e) => set("city", e.target.value)} />
          </Field>
          <Field label={t("places.district")}>
            <Input value={form.district} onChange={(e) => set("district", e.target.value)} />
          </Field>
          <Field label={t("places.lat")} hint={t("places.coordinatesHint")}>
            <Input
              type="number"
              step="any"
              min="-90"
              max="90"
              value={form.lat}
              onChange={(e) => set("lat", e.target.value)}
            />
          </Field>
          <Field label={t("places.lon")}>
            <Input
              type="number"
              step="any"
              min="-180"
              max="180"
              value={form.lon}
              onChange={(e) => set("lon", e.target.value)}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label={t("places.externalIds")} hint={t("places.externalIdsHint")}>
              <Textarea
                rows={3}
                className="font-mono text-xs"
                value={form.external_ids}
                onChange={(e) => set("external_ids", e.target.value)}
              />
            </Field>
            {jsonError ? (
              <p role="alert" className="mt-1 text-xs text-danger">
                {t("places.invalidJson")}
              </p>
            ) : null}
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
