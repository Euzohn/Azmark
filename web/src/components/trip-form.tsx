"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/lib/i18n";
import type { Trip, TripInput } from "@/lib/types";

interface TripFormProps {
  initial?: Trip;
  submitting?: boolean;
  onSubmit: (data: TripInput) => void | Promise<void>;
}

export function TripForm({ initial, submitting, onSubmit }: TripFormProps) {
  const { t } = useI18n();
  const [form, setForm] = useState({
    name: initial?.name ?? "",
    description: initial?.description ?? "",
    start_date: initial?.start_date?.slice(0, 10) ?? "",
    end_date: initial?.end_date?.slice(0, 10) ?? "",
    origin: initial?.origin ?? "",
    destination: initial?.destination ?? "",
    status: initial?.status ?? "planned",
  });

  const [formError, setFormError] = useState<string | null>(null);

  const set = (key: keyof typeof form, value: string) =>
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
      <Field label={t("trips.name")} required className="md:col-span-2">
        <Input
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder={t("trips.namePlaceholder")}
        />
      </Field>
      <Field label={t("trips.origin")}>
        <Input value={form.origin} onChange={(e) => set("origin", e.target.value)} />
      </Field>
      <Field label={t("trips.destination")}>
        <Input value={form.destination} onChange={(e) => set("destination", e.target.value)} />
      </Field>
      <Field label={t("trips.startDate")}>
        <Input
          type="date"
          value={form.start_date}
          onChange={(e) => set("start_date", e.target.value)}
        />
      </Field>
      <Field label={t("trips.endDate")}>
        <Input
          type="date"
          value={form.end_date}
          onChange={(e) => set("end_date", e.target.value)}
        />
      </Field>
      <Field label={t("trips.status")}>
        <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
          <option value="planned">{t("trips.status.planned")}</option>
          <option value="ongoing">{t("trips.status.ongoing")}</option>
          <option value="completed">{t("trips.status.completed")}</option>
        </Select>
      </Field>
      <Field label={t("trips.description")} className="md:col-span-2">
        <Textarea
          rows={3}
          value={form.description}
          onChange={(e) => set("description", e.target.value)}
        />
      </Field>
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
