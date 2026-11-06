"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus, Receipt, Search } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Fab } from "@/components/ui/fab";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { saveScroll, takeScroll } from "@/lib/scroll-memory";
import { useI18n } from "@/lib/i18n";
import type { ExpenseCategory, ExpenseFilters } from "@/lib/types";

const CATEGORIES: ExpenseCategory[] = [
  "transport",
  "accommodation",
  "food",
  "shopping",
  "entertainment",
  "other",
];

function formatDate(value: string | null, locale: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function ExpensesContent() {
  const { t, locale } = useI18n();
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");
  const [category, setCategory] = useState<ExpenseCategory | "">(
    () => (searchParams.get("category") as ExpenseCategory | null) ?? "",
  );
  const [sort, setSort] = useState<ExpenseFilters["sort"]>("newest");
  const tripId = searchParams.get("trip_id") ?? "";

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["expenses", { search, category, sort, tripId }],
    queryFn: () =>
      api.listExpenses({
        search: search || undefined,
        category: category || undefined,
        trip_id: tripId || undefined,
        sort,
        page_size: 100,
      }),
  });

  // Keep the filters in the URL so they survive a trip to the detail page.
  useEffect(() => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    if (category) query.set("category", category);
    if (tripId) query.set("trip_id", tripId);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    window.history.replaceState(null, "", `/expenses${suffix}`);
  }, [search, category, tripId]);

  const scrollRestored = useRef(false);
  useEffect(() => {
    if (scrollRestored.current || !data) return;
    scrollRestored.current = true;
    const y = takeScroll(window.location.pathname + window.location.search);
    if (y === null) return;
    window.scrollTo(0, y);
    requestAnimationFrame(() => window.scrollTo(0, y));
  }, [data]);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("expenses.title")}
        subtitle={
          data ? t("records.total", { count: data.total }) : t("expenses.subtitle")
        }
        actions={
          <Link href="/expenses/new">
            <Button className="hidden md:inline-flex">
              <Plus className="h-4 w-4" />
              {t("expenses.add")}
            </Button>
          </Link>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-10"
            placeholder={t("expenses.searchPlaceholder")}
            aria-label={t("common.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          aria-label={t("expenses.category")}
          value={category}
          onChange={(e) => setCategory(e.target.value as ExpenseCategory | "")}
          className="sm:w-44"
        >
          <option value="">{t("expenses.filterAll")}</option>
          {CATEGORIES.map((value) => (
            <option key={value} value={value}>
              {t(`expenses.category.${value}`)}
            </option>
          ))}
        </Select>
        <Select
          aria-label={t("expenses.sort.newest")}
          value={sort}
          onChange={(e) => setSort(e.target.value as ExpenseFilters["sort"])}
          className="sm:w-44"
        >
          <option value="newest">{t("expenses.sort.newest")}</option>
          <option value="oldest">{t("expenses.sort.oldest")}</option>
          <option value="amount">{t("expenses.sort.amount")}</option>
          <option value="created">{t("expenses.sort.created")}</option>
        </Select>
      </div>

      {isError ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-4 rounded-xl border border-danger/30 bg-card p-5"
        >
          <p className="text-sm text-danger">{t("common.error")}</p>
          <Button variant="outline" onClick={() => void refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      ) : isLoading ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={Receipt}
          title={t("expenses.empty")}
          hint={t("expenses.emptyHint")}
          action={
            <Link href="/expenses/new">
              <Button variant="outline">
                <Plus className="h-4 w-4" />
                {t("expenses.add")}
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {data.items.map((expense) => (
            <Link
              key={expense.id}
              href={`/expenses/${expense.id}?from=${encodeURIComponent(
                search || category
                  ? `/expenses?${new URLSearchParams({
                      ...(search ? { search } : {}),
                      ...(category ? { category } : {}),
                    }).toString()}`
                  : "/expenses",
              )}`}
              onClick={() => saveScroll(window.location.pathname + window.location.search)}
              className="group grid items-center gap-3 border-b border-border bg-card px-4 py-4 last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_8rem] lg:gap-5 lg:px-5"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <Receipt className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">
                    {expense.description || t(`expenses.category.${expense.category}`)}
                  </div>
                  <div className="mt-1 truncate text-xs text-muted-foreground lg:hidden">
                    {formatDate(expense.occurred_at, locale)}
                  </div>
                </div>
              </div>
              <div className="pl-[3.25rem] lg:pl-0">
                <Badge variant="neutral">{t(`expenses.category.${expense.category}`)}</Badge>
              </div>
              <div className="hidden text-xs text-muted-foreground lg:block">
                {formatDate(expense.occurred_at, locale)}
              </div>
              <div className="text-right text-sm font-semibold tabular-nums lg:text-right">
                {expense.amount} {expense.currency}
              </div>
            </Link>
          ))}
        </div>
      )}

      <Fab label={t("expenses.add")} href="/expenses/new">
        <Plus className="h-6 w-6" />
      </Fab>
    </div>
  );
}

export default function ExpensesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-5">
          <Skeleton className="h-10 w-56" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-20 w-full rounded-xl" />
          <Skeleton className="h-20 w-full rounded-xl" />
        </div>
      }
    >
      <ExpensesContent />
    </Suspense>
  );
}
