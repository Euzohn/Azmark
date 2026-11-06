"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus, Receipt } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ExpenseSourceType } from "@/lib/types";

interface LinkedExpensesProps {
  sourceType: ExpenseSourceType;
  sourceId: string;
}

/**
 * Spend attached to one transport record, hotel or activity (docs §6.5).
 *
 * A record can have many expenses (ticket, baggage, deposit, balance…) and the
 * list is the only place those are surfaced, so the empty state still offers
 * the explicit "record an expense" action instead of hiding the section.
 */
export function LinkedExpenses({ sourceType, sourceId }: LinkedExpensesProps) {
  const { t, locale } = useI18n();
  const pathname = usePathname();
  const { data, isLoading } = useQuery({
    queryKey: ["expenses", { source_type: sourceType, source_id: sourceId }],
    queryFn: () =>
      api.listExpenses({
        source_type: sourceType,
        source_id: sourceId,
        sort: "newest",
        page_size: 100,
      }),
  });

  const params = new URLSearchParams({
    source_type: sourceType,
    source_id: sourceId,
    return_to: pathname,
  });
  const addHref = `/expenses/new?${params.toString()}`;

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Receipt className="h-4 w-4" />
          </span>
          <div>
            <h2 className="font-display text-base font-semibold tracking-tight">
              {t("expenses.linkedTitle")}
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {isLoading
                ? t("common.loading")
                : data && data.total > 0
                  ? t("expenses.linkedCount", { count: data.total })
                  : t("expenses.linkedEmpty")}
            </p>
          </div>
        </div>
        <Link href={addHref}>
          <Button variant="outline" size="sm">
            <Plus className="h-4 w-4" />
            {t("expenses.addForSource")}
          </Button>
        </Link>
      </div>
      {isLoading ? (
        <div className="flex flex-col gap-2 p-5">
          <Skeleton className="h-10 w-full rounded-lg" />
          <Skeleton className="h-10 w-full rounded-lg" />
        </div>
      ) : data && data.items.length > 0 ? (
        <ul className="divide-y divide-border">
          {data.items.map((expense) => (
            <li key={expense.id}>
              <Link
                href={`/expenses/${expense.id}?from=${encodeURIComponent(pathname)}`}
                className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-muted/50"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {expense.description || t(`expenses.category.${expense.category}`)}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {t(`expenses.category.${expense.category}`)}
                    {expense.occurred_at
                      ? ` · ${new Date(expense.occurred_at).toLocaleDateString(locale, {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })}`
                      : ""}
                  </div>
                </div>
                <div className="shrink-0 text-sm font-semibold tabular-nums">
                  {expense.amount} {expense.currency}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
