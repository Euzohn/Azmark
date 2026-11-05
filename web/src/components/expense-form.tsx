"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

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
import { useI18n } from "@/lib/i18n";
import type { Expense, ExpenseCategory, ExpenseInput, TripList } from "@/lib/types";

const CATEGORIES: ExpenseCategory[] = [
  "transport",
  "accommodation",
  "food",
  "shopping",
  "entertainment",
  "other",
];

interface ExpenseFormProps {
  initial?: Expense;
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
  converted_amount: string;
  converted_currency: string;
  exchange_rate: string;
  exchange_rate_date: string;
}

function toForm(expense: Expense | undefined, defaultCurrency: string): FormState {
  return {
    category: expense?.category ?? "other",
    amount: expense?.amount ?? "",
    currency: expense?.currency ?? defaultCurrency,
    occurred_at: toLocalInput(expense?.occurred_at),
    description: expense?.description ?? "",
    trip_id: expense?.trip_id ?? "",
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
  return {
    category: form.category,
    amount: Number(form.amount),
    currency: form.currency.trim().toUpperCase(),
    occurred_at: form.occurred_at ? fromZonedInput(form.occurred_at) : null,
    description: form.description.trim() || null,
    trip_id: form.trip_id || null,
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
  submitting,
  onDirtyChange,
  onCancel,
  onSubmit,
}: ExpenseFormProps) {
  const { t } = useI18n();
  const { user } = useAuth();
  const [form, setForm] = useState<FormState>(() =>
    toForm(initial, user?.currency ?? ""),
  );
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
          <Field label={t("expenses.trip")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("expenses.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name}
                </option>
              ))}
            </Select>
          </Field>
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
        <Button type="submit" disabled={submitting}>
          {submitting ? t("common.loading") : t("common.save")}
        </Button>
      </div>
    </form>
  );
}
