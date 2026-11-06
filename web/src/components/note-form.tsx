"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Note, NoteInput, TripList } from "@/lib/types";

interface NoteFormProps {
  initial?: Note;
  /** Preselect the trip when the form is opened from a trip page. */
  initialTripId?: string | null;
  submitting?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onCancel?: () => void;
  onSubmit: (input: NoteInput) => void;
}

interface FormState {
  title: string;
  content: string;
  trip_id: string;
}

function toForm(note?: Note, initialTripId?: string | null): FormState {
  return {
    title: note?.title ?? "",
    content: note?.content ?? "",
    trip_id: note?.trip_id ?? initialTripId ?? "",
  };
}

function toInput(form: FormState): NoteInput {
  return {
    title: form.title.trim(),
    content: form.content.trim() || null,
    trip_id: form.trip_id || null,
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

export function NoteForm({
  initial,
  initialTripId,
  submitting,
  onDirtyChange,
  onCancel,
  onSubmit,
}: NoteFormProps) {
  const { t } = useI18n();
  const [form, setForm] = useState<FormState>(() => toForm(initial, initialTripId));
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
          <Field label={t("notes.noteTitle")}>
            <Input
              required
              value={form.title}
              maxLength={200}
              onChange={(e) => set("title", e.target.value)}
            />
          </Field>
          <Field label={t("notes.trip")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("notes.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("notes.content")}>
            <Textarea
              rows={12}
              value={form.content}
              onChange={(e) => set("content", e.target.value)}
            />
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
