"use client";

import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { Trip, TripInput } from "@/lib/types";

interface TripFormProps {
  initial?: Trip;
  submitting?: boolean;
  onSubmit: (data: TripInput) => void | Promise<void>;
}

type FieldKey =
  | "name"
  | "description"
  | "start_date"
  | "end_date"
  | "origin"
  | "destination"
  | "status";

type TripFormState = Record<FieldKey, string>;

/** The value each field would hold if untouched: the saved record, or blank. */
function snapshot(initial?: Trip): TripFormState {
  return {
    name: initial?.name ?? "",
    description: initial?.description ?? "",
    start_date: initial?.start_date?.slice(0, 10) ?? "",
    end_date: initial?.end_date?.slice(0, 10) ?? "",
    origin: initial?.origin ?? "",
    destination: initial?.destination ?? "",
    status: initial?.status ?? "planned",
  };
}

const FIELD_LABELS: Record<FieldKey, TranslationKey> = {
  name: "trips.name",
  origin: "trips.origin",
  destination: "trips.destination",
  start_date: "trips.startDate",
  end_date: "trips.endDate",
  status: "trips.status",
  description: "trips.description",
};

export function TripForm({ initial, submitting, onSubmit }: TripFormProps) {
  const { t, locale } = useI18n();
  const [form, setForm] = useState<TripFormState>(() => snapshot(initial));
  const [formError, setFormError] = useState<string | null>(null);

  const editing = Boolean(initial);
  const baseline = useMemo(() => snapshot(initial), [initial]);

  // Live diff against the saved record. Drives the per-field markers and the
  // summary next to the save button, so edits are visible before they persist.
  const changed = useMemo(() => {
    const keys = new Set<FieldKey>();
    (Object.keys(form) as FieldKey[]).forEach((key) => {
      if (form[key].trim() !== baseline[key].trim()) keys.add(key);
    });
    return keys;
  }, [form, baseline]);

  const changedLabels = editing
    ? [...changed].map((key) => t(FIELD_LABELS[key]))
    : [];
  const joiner = locale === "zh-CN" ? "、" : ", ";

  const set = (key: FieldKey, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    if (!form.name.trim()) {
      setFormError(t("trips.requiredName"));
      return;
    }
    const data: TripInput = {
      name: form.name.trim(),
      description: form.description || null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      origin: form.origin || null,
      destination: form.destination || null,
      status: form.status,
    };
    void onSubmit(data);
  };

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
      <Field
        label={t("trips.name")}
        required
        marked={changed.has("name")}
        className="md:col-span-2"
      >
        <Input
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder={t("trips.namePlaceholder")}
        />
      </Field>
      <Field label={t("trips.origin")} marked={changed.has("origin")}>
        <Input value={form.origin} onChange={(e) => set("origin", e.target.value)} />
      </Field>
      <Field label={t("trips.destination")} marked={changed.has("destination")}>
        <Input value={form.destination} onChange={(e) => set("destination", e.target.value)} />
      </Field>
      <Field label={t("trips.startDate")} marked={changed.has("start_date")}>
        <Input
          type="date"
          value={form.start_date}
          onChange={(e) => set("start_date", e.target.value)}
        />
      </Field>
      <Field label={t("trips.endDate")} marked={changed.has("end_date")}>
        <Input
          type="date"
          value={form.end_date}
          onChange={(e) => set("end_date", e.target.value)}
        />
      </Field>
      <Field label={t("trips.status")} marked={changed.has("status")}>
        <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
          <option value="planned">{t("trips.status.planned")}</option>
          <option value="ongoing">{t("trips.status.ongoing")}</option>
          <option value="completed">{t("trips.status.completed")}</option>
        </Select>
      </Field>
      <Field
        label={t("trips.description")}
        marked={changed.has("description")}
        className="md:col-span-2"
      >
        <Textarea
          rows={3}
          value={form.description}
          onChange={(e) => set("description", e.target.value)}
        />
      </Field>

      {editing ? (
        <div className="md:col-span-2">
          {changed.size > 0 ? (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-3.5 py-2.5">
              <Badge variant="primary">
                {changed.size === 1
                  ? t("trips.changedOne")
                  : t("trips.changedMany", { count: changed.size })}
              </Badge>
              <span className="text-sm text-foreground/80">{changedLabels.join(joiner)}</span>
            </div>
          ) : (
            <p className="px-0.5 text-sm text-muted-foreground">{t("trips.noChanges")}</p>
          )}
        </div>
      ) : null}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" disabled={submitting}>
          {t("common.save")}
        </Button>
        {formError ? <span className="text-sm text-danger">{formError}</span> : null}
      </div>
    </form>
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
            {t("trips.changedMarker")}
          </span>
        ) : null}
      </Label>
      {children}
    </div>
  );
}
