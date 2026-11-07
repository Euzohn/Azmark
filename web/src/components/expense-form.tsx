"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CurrencySelect } from "@/components/ui/currency-select";
import { DateInput, DateTimeLocalInput } from "@/components/ui/date-input";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { fromZonedInput, toLocalInput } from "@/lib/datetime";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type {
  Activity,
  Expense,
  ExpenseCategory,
  ExpenseInput,
  ExpenseSourceType,
  Hotel,
  TimelineRecord,
  TripList,
} from "@/lib/types";

export interface ExpenseSourceRef {
  type: ExpenseSourceType;
  id: string;
}

const CATEGORIES: ExpenseCategory[] = [
  "transport",
  "accommodation",
  "food",
  "shopping",
  "entertainment",
  "other",
];

const SOURCE_LABEL_KEYS: Record<ExpenseSourceType, TranslationKey> = {
  transport: "expenses.sourceType.transport",
  hotel: "expenses.sourceType.hotel",
  activity: "expenses.sourceType.activity",
};

const SOURCE_TYPES: ExpenseSourceType[] = ["transport", "hotel", "activity"];

function transportOptionLabel(record: TimelineRecord): string {
  const route = [record.origin, record.destination].filter(Boolean).join(" → ");
  const service = record.service_number || record.carrier || "";
  return [service, route].filter(Boolean).join(" · ") || record.id;
}

function hotelOptionLabel(hotel: Hotel): string {
  return [hotel.hotel, hotel.check_in].filter(Boolean).join(" · ");
}

function activityOptionLabel(activity: Activity): string {
  const date = activity.start_at ? activity.start_at.slice(0, 10) : "";
  return [activity.name, date].filter(Boolean).join(" · ") || activity.id;
}

interface ExpenseFormProps {
  initial?: Expense;
  /** Pre-link a new spend to the record the user came from. */
  source?: ExpenseSourceRef | null;
  /** Preselect a trip for an independent spend (docs §6.3). */
  initialTripId?: string | null;
  submitting?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onCancel?: () => void;
  onSubmit: (input: ExpenseInput) => void;
}

interface FormState {
  category: ExpenseCategory;
  amount: string;
  currency: string;
  occurred_at: string;
  description: string;
  trip_id: string;
  source_type: ExpenseSourceType | "";
  source_id: string;
  converted_amount: string;
  converted_currency: string;
  exchange_rate: string;
  exchange_rate_date: string;
}

function toForm(
  expense: Expense | undefined,
  defaultCurrency: string,
  source: ExpenseSourceRef | null | undefined,
  initialTripId: string | null | undefined,
): FormState {
  return {
    category: expense?.category ?? "other",
    amount: expense?.amount ?? "",
    currency: expense?.currency ?? defaultCurrency,
    occurred_at: toLocalInput(expense?.occurred_at),
    description: expense?.description ?? "",
    trip_id: expense?.trip_id ?? initialTripId ?? "",
    source_type: expense?.source_type ?? source?.type ?? "",
    source_id: expense?.source_id ?? source?.id ?? "",
    converted_amount: expense?.converted_amount ?? "",
    converted_currency: expense?.converted_currency ?? "",
    exchange_rate: expense?.exchange_rate ?? "",
    exchange_rate_date: expense?.exchange_rate_date ?? "",
  };
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function toInput(form: FormState): ExpenseInput {
  const linked = form.source_type !== "" && form.source_id !== "";
  return {
    category: form.category,
    amount: Number(form.amount),
    currency: form.currency.trim().toUpperCase(),
    occurred_at: form.occurred_at ? fromZonedInput(form.occurred_at) : null,
    description: form.description.trim() || null,
    // A linked expense derives its trip from the source; sending a value would
    // either duplicate the derivation or trip the conflict check (docs §6.3).
    // Explicit nulls let the update endpoint unbind a previously linked spend.
    ...(linked
      ? { source_type: form.source_type as ExpenseSourceType, source_id: form.source_id }
      : { trip_id: form.trip_id || null, source_type: null, source_id: null }),
    converted_amount: optionalNumber(form.converted_amount),
    converted_currency: form.converted_currency.trim().toUpperCase() || null,
    exchange_rate: optionalNumber(form.exchange_rate),
    exchange_rate_date: form.exchange_rate_date || null,
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

export function ExpenseForm({
  initial,
  source,
  initialTripId,
  submitting,
  onDirtyChange,
  onCancel,
  onSubmit,
}: ExpenseFormProps) {
  const { t } = useI18n();
  const { user } = useAuth();
  const [form, setForm] = useState<FormState>(() =>
    toForm(initial, user?.currency ?? "", source, initialTripId),
  );
  const sourceBound = form.source_type !== "" && form.source_id !== "";
  const sourceIncomplete = form.source_type !== "" && form.source_id === "";
  const { data: trips } = useQuery<TripList>({
    queryKey: ["trips", { page_size: 100 }],
    queryFn: () => api.listTrips({ page_size: 100 }),
  });

  const transportSources = useQuery({
    queryKey: ["records", { page_size: 100, sort: "newest" }],
    queryFn: () => api.listRecords({ page_size: 100, sort: "newest" }),
    enabled: form.source_type === "transport",
  });
  const hotelSources = useQuery({
    queryKey: ["hotels", { page_size: 100, sort: "newest" }],
    queryFn: () => api.listHotels({ page_size: 100, sort: "newest" }),
    enabled: form.source_type === "hotel",
  });
  const activitySources = useQuery({
    queryKey: ["activities", { page_size: 100, sort: "newest" }],
    queryFn: () => api.listActivities({ page_size: 100, sort: "newest" }),
    enabled: form.source_type === "activity",
  });

  const sourceOptions = useMemo(() => {
    if (form.source_type === "transport") {
      return (transportSources.data?.items ?? []).map((record) => ({
        id: record.id,
        label: transportOptionLabel(record),
      }));
    }
    if (form.source_type === "hotel") {
      return (hotelSources.data?.items ?? []).map((hotel) => ({
        id: hotel.id,
        label: hotelOptionLabel(hotel),
      }));
    }
    if (form.source_type === "activity") {
      return (activitySources.data?.items ?? []).map((activity) => ({
        id: activity.id,
        label: activityOptionLabel(activity),
      }));
    }
    return [];
  }, [
    form.source_type,
    transportSources.data,
    hotelSources.data,
    activitySources.data,
  ]);

  const sourceLoading =
    (form.source_type === "transport" && transportSources.isLoading) ||
    (form.source_type === "hotel" && hotelSources.isLoading) ||
    (form.source_type === "activity" && activitySources.isLoading);
  const currentSourceMissing =
    form.source_id !== "" && !sourceOptions.some((option) => option.id === form.source_id);

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
          <Field label={t("expenses.category")}>
            <Select
              value={form.category}
              onChange={(e) => set("category", e.target.value as ExpenseCategory)}
            >
              {CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {t(`expenses.category.${category}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("expenses.source")}>
            <Select
              value={form.source_type}
              onChange={(e) => {
                const next = e.target.value as ExpenseSourceType | "";
                setForm((prev) => ({ ...prev, source_type: next, source_id: "" }));
                onDirtyChange?.(true);
              }}
            >
              <option value="">{t("expenses.sourceNone")}</option>
              {SOURCE_TYPES.map((sourceType) => (
                <option key={sourceType} value={sourceType}>
                  {t(SOURCE_LABEL_KEYS[sourceType])}
                </option>
              ))}
            </Select>
          </Field>
          {form.source_type !== "" ? (
            <div className="sm:col-span-2">
              <Field label={t("expenses.sourceRecord")}>
                <Select
                  value={form.source_id}
                  disabled={sourceLoading}
                  onChange={(e) => set("source_id", e.target.value)}
                >
                  <option value="">
                    {sourceLoading
                      ? t("expenses.sourceLoading")
                      : sourceOptions.length > 0
                        ? t("expenses.sourceSelectPlaceholder")
                        : t("expenses.sourceEmpty")}
                  </option>
                  {currentSourceMissing ? (
                    <option value={form.source_id}>{t("expenses.sourceCurrent")}</option>
                  ) : null}
                  {sourceOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
          ) : null}
          <Field label={t("expenses.trip")}>
            {sourceBound ? (
              <div className="flex h-10 items-center rounded-lg border border-border bg-muted/40 px-3 text-sm text-muted-foreground">
                {t("expenses.sourceHint")}
              </div>
            ) : (
              <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
                <option value="">{t("expenses.tripNone")}</option>
                {trips?.items.map((trip) => (
                  <option key={trip.id} value={trip.id}>
                    {trip.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {sourceIncomplete ? (
            <p className="text-xs text-danger sm:col-span-2">{t("expenses.sourceRequired")}</p>
          ) : null}
          <Field label={t("expenses.amount")}>
            <Input
              required
              type="number"
              step="0.01"
              min="0"
              value={form.amount}
              onChange={(e) => set("amount", e.target.value)}
            />
          </Field>
          <Field label={t("expenses.currency")}>
            <CurrencySelect
              required
              value={form.currency}
              onChange={(value) => set("currency", value)}
            />
          </Field>
          <Field label={t("expenses.occurredAt")}>
            <DateTimeLocalInput
              value={form.occurred_at}
              onChange={(e) => set("occurred_at", e.target.value)}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label={t("expenses.description")}>
              <Textarea
                rows={2}
                value={form.description}
                onChange={(e) => set("description", e.target.value)}
              />
            </Field>
          </div>
          <div className="mt-2 border-t border-border pt-4 sm:col-span-2">
            <p className="text-xs font-medium text-muted-foreground">
              {t("expenses.conversionTitle")}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {t("expenses.conversionHint")}
            </p>
          </div>
          <Field label={t("expenses.convertedAmount")}>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.converted_amount}
              onChange={(e) => set("converted_amount", e.target.value)}
            />
          </Field>
          <Field label={t("expenses.convertedCurrency")}>
            <CurrencySelect
              value={form.converted_currency}
              onChange={(value) => set("converted_currency", value)}
            />
          </Field>
          <Field label={t("expenses.exchangeRate")}>
            <Input
              type="number"
              step="any"
              min="0"
              value={form.exchange_rate}
              onChange={(e) => set("exchange_rate", e.target.value)}
            />
          </Field>
          <Field label={t("expenses.exchangeRateDate")}>
            <DateInput
              value={form.exchange_rate_date}
              onChange={(e) => set("exchange_rate_date", e.target.value)}
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
        <Button type="submit" disabled={submitting || sourceIncomplete}>
          {submitting ? t("common.loading") : t("common.save")}
        </Button>
      </div>
    </form>
  );
}
