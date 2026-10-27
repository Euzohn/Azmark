"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BarChart3,
  Bus,
  CalendarDays,
  MapPin,
  Plane,
  PlaneTakeoff,
  TrainFront,
} from "lucide-react";
import Link from "next/link";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { AirportName } from "@/components/airport-name";
import { ColumnChart, ShareBar, type ChartDatum } from "@/components/charts";
import { PageHeader } from "@/components/page-header";
import { FlightStatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Stat } from "@/components/ui/stat";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { daysUntilDeparture, formatZonedDateTime } from "@/lib/datetime";
import { useI18n } from "@/lib/i18n";
import type { BreakdownItem, DashboardRecord } from "@/lib/types";

function recordHref(record: DashboardRecord): string {
  if (record.type === "train") return `/trains/${record.id}`;
  if (record.type === "other") return `/transports/${record.id}`;
  return `/flights/${record.id}`;
}

function RecordTypeIcon({ type, className = "h-4 w-4" }: { type: string; className?: string }) {
  if (type === "train") return <TrainFront className={className} />;
  if (type === "other") return <Bus className={className} />;
  return <Plane className={className} />;
}

/** Fill missing months so the trend reads as a continuous time axis. */
function rollingMonths(items: BreakdownItem[], count = 12): { key: string; count: number; date: Date }[] {
  const counts = new Map(items.map((item) => [item.label, item.count]));
  const now = new Date();
  let end = new Date(now.getFullYear(), now.getMonth(), 1);

  const latest = items.at(-1)?.label;
  if (latest) {
    const [year, month] = latest.split("-").map(Number);
    const latestDate = new Date(year, month - 1, 1);
    if (latestDate > end) end = latestDate;
  }

  return Array.from({ length: count }, (_, index) => {
    const date = new Date(end.getFullYear(), end.getMonth() - (count - 1 - index), 1);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    return { key, count: counts.get(key) ?? 0, date };
  });
}

function RecordRow({ record, delay = 0 }: { record: DashboardRecord; delay?: number }) {
  const { locale } = useI18n();
  const dateLabel = formatZonedDateTime(
    record.departure_time,
    locale,
    record.departure_timezone,
    {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    },
  );

  return (
    <Link
      href={recordHref(record)}
      className="flex animate-fade-in-up items-center gap-3 rounded-xl px-2 py-2.5 transition-all duration-200 hover:bg-accent hover:pl-3"
      style={{ animationDelay: `${delay}ms` }}
    >
      {record.type === "flight" ? (
        <AirlineLogo code={record.airline_code} className="h-9 w-9" />
      ) : (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
          <RecordTypeIcon type={record.type} />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 truncate text-sm font-medium">
          <span className="truncate">
            {record.origin ? <AirportName value={record.origin} /> : "—"}
          </span>
          <ArrowRight className="h-3.5 w-3.5 shrink-0 text-primary" strokeWidth={2.5} />
          <span className="truncate">
            {record.destination ? <AirportName value={record.destination} /> : "—"}
          </span>
          {record.service_number ? (
            <span className="ml-1 shrink-0 text-xs font-normal text-muted-foreground">
              {record.service_number}
            </span>
          ) : null}
        </div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">{dateLabel}</div>
      </div>
      <FlightStatusBadge status={record.status} />
    </Link>
  );
}

function UpcomingTicket({ record }: { record: DashboardRecord }) {
  const { t, locale } = useI18n();
  const departure = record.departure_time ? new Date(record.departure_time) : null;
  const valid = departure && !Number.isNaN(departure.getTime()) ? departure : null;
  const days = daysUntilDeparture(record.departure_time, record.departure_timezone);
  const formatDeparture = (options: Intl.DateTimeFormatOptions) =>
    formatZonedDateTime(record.departure_time, locale, record.departure_timezone, options);

  const countdown =
    days === null
      ? null
      : days < 0
        ? t("dashboard.departed")
        : days === 0
          ? t("dashboard.departsToday")
          : days === 1
            ? t("dashboard.departsTomorrow")
            : t("dashboard.departsInDays", { days });

  return (
    <Card className="relative animate-fade-in-up overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#e0a737] via-primary to-[#96670c]" />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-primary/5 blur-2xl"
      />

      <CardContent className="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-stretch sm:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.16em] text-primary">
              <PlaneTakeoff className="h-3.5 w-3.5" />
              {t("dashboard.upcoming")}
            </span>
            {countdown ? <Badge variant="primary">{countdown}</Badge> : null}
            {record.service_number ? <Badge>{record.service_number}</Badge> : null}
          </div>

          <Link href={recordHref(record)} className="group flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              <span>{record.origin ?? "—"}</span>
              <ArrowRight
                className="h-6 w-6 text-primary transition-transform duration-200 group-hover:translate-x-1 sm:h-7 sm:w-7"
                strokeWidth={2}
              />
              <span>{record.destination ?? "—"}</span>
            </div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
              <span>
                <AirportName value={record.origin} />
              </span>
              <span aria-hidden>·</span>
              <span>
                <AirportName value={record.destination} />
              </span>
            </div>
          </Link>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
              <CalendarDays className="h-4 w-4 text-primary/80" />
              {valid
                ? formatDeparture({
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                    timeZoneName: "short",
                  })
                : "—"}
            </span>
            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
              {record.type === "flight" ? (
                <AirlineName code={record.airline_code} fallback={record.carrier} />
              ) : (
                <>{record.carrier ?? record.service_number ?? "—"}</>
              )}
            </span>
            <FlightStatusBadge status={record.status} />
          </div>
        </div>

        {valid ? (
          <div className="flex shrink-0 items-center gap-5 rounded-2xl border border-border bg-muted/40 px-5 py-4 sm:flex-col sm:items-center sm:justify-center sm:gap-1">
            <div className="text-center">
              <div className="font-display text-4xl font-semibold leading-none tabular-nums text-foreground">
                {formatDeparture({ day: "2-digit" })}
              </div>
              <div className="mt-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                {formatDeparture({ month: "short" })}
              </div>
            </div>
            <div className="hidden h-px w-10 bg-border sm:block" />
            <div className="text-center">
              <div className="text-lg font-semibold tabular-nums text-foreground">
                {formatDeparture({ hour: "2-digit", minute: "2-digit" })}
              </div>
              <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                {formatDeparture({ weekday: "short" })}
              </div>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { t, locale } = useI18n();
  const { user } = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.getDashboard,
  });

  const name = user?.display_name ?? user?.username ?? "";
  const stats = data?.stats;
  const hasRecords = (stats?.journeys ?? 0) > 0;

  const metrics = [
    { label: t("dashboard.stats.countries"), value: stats?.countries ?? 0 },
    { label: t("dashboard.stats.cities"), value: stats?.cities ?? 0 },
    { label: t("dashboard.stats.journeys"), value: stats?.journeys ?? 0 },
    {
      label: t("dashboard.stats.distance"),
      value: `${Math.round(stats?.distance_km ?? 0).toLocaleString(locale)} ${t("stats.km")}`,
    },
  ];

  const composition: ChartDatum[] = [
    { label: t("dashboard.stats.flights"), value: stats?.flights ?? 0 },
    { label: t("dashboard.stats.trains"), value: stats?.trains ?? 0 },
    { label: t("dashboard.stats.transports"), value: stats?.transports ?? 0 },
  ];

  const monthFmt = new Intl.DateTimeFormat(locale, { month: "short" });
  const trend = rollingMonths(data?.by_month ?? []);
  const trendTotal = trend.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={name ? t("dashboard.greeting", { name }) : t("dashboard.title")}
        subtitle={t("app.tagline")}
        actions={
          <Link href="/statistics">
            <Button variant="ghost" size="sm">
              <BarChart3 className="h-4 w-4" />
              {t("dashboard.viewStats")}
            </Button>
          </Link>
        }
      />

      {isLoading ? (
        <div className="flex flex-col gap-6">
          <Skeleton className="h-44 w-full rounded-2xl" />
          <Skeleton className="h-24 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      ) : null}

      {!isLoading && !hasRecords ? (
        <EmptyState
          icon={PlaneTakeoff}
          title={t("dashboard.empty")}
          hint={t("dashboard.emptyHint")}
          action={
            <Link href="/flights/new">
              <Button>
                <Plane className="h-4 w-4" />
                {t("flights.add")}
              </Button>
            </Link>
          }
        />
      ) : null}

      {!isLoading && hasRecords ? (
        <>
          {data?.upcoming ? (
            <UpcomingTicket record={data.upcoming} />
          ) : (
            <Card className="animate-fade-in-up border-dashed bg-transparent shadow-none">
              <CardContent className="flex flex-wrap items-center justify-between gap-3 p-5">
                <div>
                  <div className="font-display text-base font-semibold">
                    {t("dashboard.noUpcoming")}
                  </div>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {t("dashboard.noUpcomingHint")}
                  </p>
                </div>
                <Link href="/flights/new">
                  <Button variant="outline" size="sm">
                    <Plane className="h-4 w-4" />
                    {t("flights.add")}
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}

          {/* Footprint — the only totals on this page */}
          <Card className="animate-fade-in-up" style={{ animationDelay: "120ms" }}>
            <CardContent className="flex flex-col gap-5 p-0">
              <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-4">
                {metrics.map((metric) => (
                  <div key={metric.label} className="bg-card p-4">
                    <Stat label={metric.label} value={metric.value} />
                  </div>
                ))}
              </div>
              <div className="flex flex-col gap-4 px-5 pb-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 flex-1 sm:max-w-md">
                  <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                    {t("dashboard.composition")}
                  </div>
                  <ShareBar data={composition} ariaLabel={t("dashboard.composition")} />
                </div>
                {stats?.trips ? (
                  <div className="flex items-center gap-2 rounded-xl border border-border bg-muted/40 px-4 py-2.5">
                    <MapPin className="h-4 w-4 text-primary" />
                    <span className="font-display text-xl font-semibold tabular-nums">
                      {stats.trips}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {t("dashboard.stats.trips")}
                    </span>
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-5">
            <Card
              className="animate-fade-in-up lg:col-span-3"
              style={{ animationDelay: "240ms" }}
            >
              <CardHeader className="flex-row items-start justify-between gap-3">
                <div>
                  <CardTitle>{t("dashboard.trend")}</CardTitle>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("dashboard.trendHint", { count: trendTotal })}
                  </p>
                </div>
                <CalendarDays className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <ColumnChart
                  data={trend.map((item) => ({ label: item.key, value: item.count }))}
                  ariaLabel={t("dashboard.trend")}
                  formatLabel={(label) => {
                    const [year, month] = label.split("-").map(Number);
                    return monthFmt.format(new Date(year, month - 1, 1));
                  }}
                />
              </CardContent>
            </Card>

            <Card className="animate-fade-in-up lg:col-span-2" style={{ animationDelay: "300ms" }}>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>{t("dashboard.recent")}</CardTitle>
                <Link href="/records">
                  <Button variant="ghost" size="sm">
                    {t("dashboard.viewAll")}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </CardHeader>
              <CardContent className="flex flex-col gap-1">
                {data && data.recent.length > 0 ? (
                  data.recent.map((record, index) => (
                    <RecordRow key={record.id} record={record} delay={360 + index * 40} />
                  ))
                ) : (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    {t("dashboard.recentEmpty")}
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
