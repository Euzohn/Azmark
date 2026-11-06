"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MoreHorizontal, Link2, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ExpenseForm } from "@/components/expense-form";
import { PageHeader } from "@/components/page-header";
import { TripLinkCard } from "@/components/trip-link-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Expense, ExpenseInput, ExpenseSourceType } from "@/lib/types";

function sourceHref(type: ExpenseSourceType, id: string): string | null {
  if (type === "hotel") return `/hotels/${id}`;
  if (type === "activity") return `/activities/${id}`;
  return null;
}

function expenseReturnHref(from: string | null): string {
  if (from && from.startsWith("/expenses")) return from;
  return "/expenses";
}

function formatDateTime(value: string | null, locale: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ExpenseDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const backHref = expenseReturnHref(searchParams.get("from"));
  const queryClient = useQueryClient();
  const { t, locale } = useI18n();
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [saved, setSaved] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["expense", id],
    queryFn: () => api.getExpense(id),
    enabled: Boolean(id),
  });

  const update = useMutation({
    mutationFn: (input: ExpenseInput) => api.updateExpense(id, input),
    onSuccess: async (expense) => {
      queryClient.setQueryData(["expense", id], expense);
      setDirty(false);
      setEditing(false);
      setSaved(true);
      await Promise.all(
        ["expenses", "expense", "trips", "trip", "dashboard"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteExpense(id),
    onSuccess: async () => {
      await Promise.all(
        ["expenses", "expense", "trips", "trip", "dashboard"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
      router.replace(backHref);
    },
  });

  const cancel = () => {
    if (dirty && !window.confirm(t("common.unsaved"))) return;
    setDirty(false);
    setEditing(false);
    update.reset();
  };

  if (isLoading) return <DetailSkeleton />;
  if (isError) {
    return (
      <div role="alert" className="flex items-center gap-4">
        <p className="text-sm text-danger">{t("common.error")}</p>
        <Button variant="outline" onClick={() => void refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }
  if (!data) return <p>{t("common.empty")}</p>;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={t(editing ? "expenses.edit" : "expenses.detail")}
        backHref={backHref}
        backLabel={t("common.back")}
        actions={
          editing ? undefined : (
            <>
              <Button
                variant="outline"
                onClick={() => {
                  setSaved(false);
                  setEditing(true);
                }}
              >
                <Pencil className="h-4 w-4" />
                {t("common.edit")}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("common.actions")}
                onClick={() => setMoreOpen(true)}
              >
                <MoreHorizontal className="h-5 w-5" />
              </Button>
            </>
          )
        }
      />
      {saved && !editing ? (
        <p role="status" className="text-sm text-success">
          {t("common.saved")}
        </p>
      ) : null}
      {editing ? (
        <>
          {update.isError ? (
            <p role="alert" className="text-sm text-danger">
              {t("common.error")}
            </p>
          ) : null}
          <ExpenseForm
            initial={data}
            submitting={update.isPending}
            onDirtyChange={setDirty}
            onCancel={cancel}
            onSubmit={(input) => update.mutate(input)}
          />
        </>
      ) : (
        <>
          <ExpenseSummary expense={data} locale={locale} />
          {data.trip_id ? (
            <TripLinkCard tripId={data.trip_id} label={t("expenses.trip")} />
          ) : null}
          {data.source_type && data.source_id ? (
            <ExpenseSourceCard sourceType={data.source_type} sourceId={data.source_id} />
          ) : null}
        </>
      )}
      <Dialog
        open={moreOpen}
        onClose={() => setMoreOpen(false)}
        title={t("common.actions")}
        variant="responsive"
      >
        <Button
          variant="ghost"
          className="w-full justify-start text-danger"
          onClick={() => {
            setMoreOpen(false);
            setDeleteOpen(true);
          }}
        >
          <Trash2 className="h-4 w-4" />
          {t("common.delete")}
        </Button>
      </Dialog>
      <Dialog
        open={deleteOpen}
        onClose={() => {
          if (!remove.isPending) setDeleteOpen(false);
        }}
        title={t("common.confirmDelete")}
        variant="responsive"
      >
        <p className="text-sm text-muted-foreground">{t("expenses.deleteConfirm")}</p>
        {remove.isError ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {t("common.error")}
          </p>
        ) : null}
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="outline"
            disabled={remove.isPending}
            onClick={() => setDeleteOpen(false)}
          >
            {t("common.cancel")}
          </Button>
          <Button variant="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
            {t(remove.isPending ? "common.loading" : "common.delete")}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

const SOURCE_LABELS: Record<ExpenseSourceType, TranslationKey> = {
  transport: "expenses.sourceType.transport",
  hotel: "expenses.sourceType.hotel",
  activity: "expenses.sourceType.activity",
};

function ExpenseSourceCard({
  sourceType,
  sourceId,
}: {
  sourceType: ExpenseSourceType;
  sourceId: string;
}) {
  const { t } = useI18n();
  const href = sourceHref(sourceType, sourceId);
  const content = (
    <>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Link2 className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <div className="text-xs text-muted-foreground">{t("expenses.source")}</div>
        <div className="truncate text-sm font-medium">{t(SOURCE_LABELS[sourceType])}</div>
      </div>
    </>
  );
  const className =
    "flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-4 transition-colors";
  return href ? (
    <Link href={href} className={`${className} hover:border-primary/40`}>
      {content}
    </Link>
  ) : (
    <div className={className}>{content}</div>
  );
}

function ExpenseSummary({ expense, locale }: { expense: Expense; locale: string }) {  const { t } = useI18n();
  const fields: [TranslationKey, string | null][] = [
    ["expenses.category", t(`expenses.category.${expense.category}`)],
    ["expenses.occurredAt", formatDateTime(expense.occurred_at, locale)],
    ["expenses.amount", `${expense.amount} ${expense.currency}`],
    ["expenses.description", expense.description],
    [
      "expenses.convertedAmount",
      expense.converted_amount != null
        ? `${expense.converted_amount} ${expense.converted_currency ?? ""}`.trim()
        : null,
    ],
    ["expenses.exchangeRate", expense.exchange_rate],
    ["expenses.exchangeRateDate", expense.exchange_rate_date],
  ];

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 md:px-7">
        <div className="min-w-0">
          <div className="font-display text-lg font-semibold tracking-tight">
            {expense.description || t(`expenses.category.${expense.category}`)}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {formatDateTime(expense.occurred_at, locale)}
          </div>
        </div>
        <Badge variant="neutral">{t(`expenses.category.${expense.category}`)}</Badge>
      </div>
      <dl className="grid gap-x-6 gap-y-3 px-5 py-5 sm:grid-cols-2 md:px-7">
        {fields.map(([key, value]) => (
          <div key={key} className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {t(key)}
            </dt>
            <dd className="text-sm text-foreground">{value || "—"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function DetailSkeleton() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Skeleton className="h-12 w-64" />
      <Skeleton className="h-52 w-full rounded-xl" />
    </div>
  );
}

export default function ExpenseDetailPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <ExpenseDetail />
    </Suspense>
  );
}
