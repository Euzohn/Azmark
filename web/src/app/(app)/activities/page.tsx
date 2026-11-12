"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarDays, Plus, Search } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Fab } from "@/components/ui/fab";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { usePageTitle } from "@/lib/page-title";
import type { ActivityType } from "@/lib/types";

const TYPES: ActivityType[] = [
  "sightseeing",
  "theme_park",
  "museum",
  "culture",
  "outdoor",
  "sports",
  "dining",
  "shopping",
  "entertainment",
  "event",
  "experience",
  "wellness",
  "visit",
  "other",
];

function formatDate(value: string | null, locale: string): string {
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

function ActivitiesContent() {
  const { t, locale } = useI18n();
  usePageTitle(t("nav.activities"));
  const [search, setSearch] = useState("");
  const [type, setType] = useState<ActivityType | "">("");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["activities", { search, type }],
    queryFn: () =>
      api.listActivities({
        search: search || undefined,
        type: type || undefined,
        page_size: 100,
      }),
  });

  useEffect(() => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    if (type) query.set("type", type);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    window.history.replaceState(null, "", `/activities${suffix}`);
  }, [search, type]);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("activities.title")}
        subtitle={
          data ? t("records.total", { count: data.total }) : t("activities.subtitle")
        }
        actions={
          <Link href="/activities/new">
            <Button className="hidden md:inline-flex">
              <Plus className="h-4 w-4" />
              {t("activities.add")}
            </Button>
          </Link>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-10"
            placeholder={t("activities.searchPlaceholder")}
            aria-label={t("common.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          aria-label={t("activities.type")}
          value={type}
          onChange={(e) => setType(e.target.value as ActivityType | "")}
          className="sm:w-48"
        >
          <option value="">{t("activities.filterAll")}</option>
          {TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`activities.type.${value}`)}
            </option>
          ))}
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
          icon={CalendarDays}
          title={t("activities.empty")}
          hint={t("activities.emptyHint")}
          action={
            <Link href="/activities/new">
              <Button variant="outline">
                <Plus className="h-4 w-4" />
                {t("activities.add")}
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {data.items.map((activity) => (
            <Link
              key={activity.id}
              href={`/activities/${activity.id}`}
              className="group grid items-center gap-3 border-b border-border bg-card px-4 py-4 last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_8rem] lg:gap-5 lg:px-5"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <CalendarDays className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{activity.name}</div>
                  <div className="mt-1 truncate text-xs text-muted-foreground lg:hidden">
                    {formatDate(activity.start_at, locale)}
                  </div>
                </div>
              </div>
              <div className="pl-[3.25rem] lg:pl-0">
                <Badge variant="neutral">{t(`activities.type.${activity.type}`)}</Badge>
              </div>
              <div className="hidden text-xs text-muted-foreground lg:block">
                {formatDate(activity.start_at, locale)}
              </div>
              <div className="text-right text-sm font-semibold tabular-nums">
                {activity.price ? `${activity.price} ${activity.currency ?? ""}`.trim() : "—"}
              </div>
            </Link>
          ))}
        </div>
      )}

      <Fab label={t("activities.add")} href="/activities/new">
        <Plus className="h-6 w-6" />
      </Fab>
    </div>
  );
}

export default function ActivitiesPage() {
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
      <ActivitiesContent />
    </Suspense>
  );
}
