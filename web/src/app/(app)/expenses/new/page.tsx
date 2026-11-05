"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ExpenseForm } from "@/components/expense-form";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ExpenseInput } from "@/lib/types";

export default function NewExpensePage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (data: ExpenseInput) => api.createExpense(data),
    onSuccess: () => {
      for (const key of ["expenses", "trips", "trip", "dashboard"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      router.push("/expenses");
    },
    onError: () => setError(t("common.error")),
  });

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={t("expenses.add")}
        backHref="/expenses"
        backLabel={t("common.back")}
      />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <ExpenseForm
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
