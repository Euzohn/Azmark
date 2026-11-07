"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";

import { ExpenseForm, type ExpenseSourceRef } from "@/components/expense-form";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ExpenseInput, ExpenseSourceType } from "@/lib/types";
import { uuid } from "@/lib/uuid";

const SOURCE_TYPES: ExpenseSourceType[] = ["transport", "hotel", "activity"];

function localReturnHref(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;
  return value;
}

function NewExpenseContent() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const submitKey = useRef<{ key: string; payload: string } | null>(null);

  const rawSourceType = searchParams.get("source_type");
  const sourceId = searchParams.get("source_id");
  const source: ExpenseSourceRef | null =
    rawSourceType && sourceId && SOURCE_TYPES.includes(rawSourceType as ExpenseSourceType)
      ? { type: rawSourceType as ExpenseSourceType, id: sourceId }
      : null;
  const initialTripId = searchParams.get("trip_id");
  const returnTo = localReturnHref(searchParams.get("return_to")) ?? "/expenses";

  const create = useMutation({
    mutationFn: (data: ExpenseInput) => {
      // A retried submit reuses its key; an edited payload gets a new one so
      // the key never pins the first (rejected) request (docs §4.3).
      const payload = JSON.stringify(data);
      if (!submitKey.current || submitKey.current.payload !== payload) {
        submitKey.current = { key: uuid(), payload };
      }
      return api.createExpense(data, submitKey.current.key);
    },
    onSuccess: () => {
      submitKey.current = null;
      for (const key of ["expenses", "trips", "trip", "dashboard"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      router.push(returnTo);
    },
    onError: () => setError(t("common.error")),
  });

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={t("expenses.add")}
        backHref={source ? returnTo : "/expenses"}
        backLabel={t("common.back")}
      />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <ExpenseForm
          source={source}
          initialTripId={initialTripId}
          submitting={create.isPending}
          onSubmit={(data) => {
            setError(null);
            create.mutate(data);
          }}
        />
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
    </div>
  );
}

export default function NewExpensePage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto flex max-w-5xl flex-col gap-6">
          <Skeleton className="h-12 w-64" />
          <Skeleton className="h-80 w-full rounded-xl" />
        </div>
      }
    >
      <NewExpenseContent />
    </Suspense>
  );
}
