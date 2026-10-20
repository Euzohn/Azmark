"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BarChart3,
  Bus,
  Plane,
  PlaneTakeoff,
  TrainFront,
} from "lucide-react";
import Link from "next/link";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { FlightStatusBadge } from "@/components/status-badge";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Stat } from "@/components/ui/stat";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";
import type { DashboardRecord } from "@/lib/types";

function formatDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function recordHref(record: DashboardRecord): string {
  if (record.type === "train") return `/trains/${record.id}`;
  if (record.type === "other") return `/transports/${record.id}`;
  return `/flights/${record.id}`;
}

function RecordTypeIcon({ type }: { type: string }) {
  if (type === "train") return <TrainFront className="h-4 w-4" />;
  if (type === "other") return <Bus className="h-4 w-4" />;
  return <Plane className="h-4 w-4" />;
}

function RecordRow({ record, delay = 0 }: { record: DashboardRecord; delay?: number }) {
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
          <span>{record.origin ?? "—"}</span>
          <ArrowRight className="h-3.5 w-3.5 shrink-0 text-primary" strokeWidth={2.5} />
          <span>{record.destination ?? "—"}</span>
          {record.service_number ? (
            <span className="ml-1 shrink-0 text-xs font-normal text-muted-foreground">
              {record.service_number}
            </span>
          ) : null}
        </div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">
          {formatDate(record.departure_time)}
        </div>
      </div>
      <FlightStatusBadge status={record.status} />
    </Link>
  );
}

export default function DashboardPage() {
  const { t } = useI18n();
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
      value: `${Math.round(stats?.distance_km ?? 0).toLocaleString()} ${t("stats.km")}`,
    },
  ];

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
          <Skeleton className="h-28 w-full rounded-2xl" />
          <Skeleton className="h-20 w-full rounded-2xl" />
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
          {/* Next departure hero */}
          {data?.upcoming ? (
            <Card
              interactive
              className="animate-fade-in-up overflow-hidden"
              style={{ animationDelay: "120ms" }}
            >
              <div className="h-1 w-full bg-gradient-to-r from-[#e0a737] via-primary to-[#96670c]" />
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <PlaneTakeoff className="h-4 w-4 text-primary" />
                  {t("dashboard.upcoming")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Link href={recordHref(data.upcoming)} className="flex items-center gap-4">
                  {data.upcoming.type === "flight" ? (
                    <AirlineLogo code={data.upcoming.airline_code} className="h-12 w-12" />
                  ) : (
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
                      <RecordTypeIcon type={data.upcoming.type} />
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="font-display text-2xl font-semibold tracking-tight">
                      {data.upcoming.origin ?? "—"}
                      <ArrowRight
                        className="mx-2 inline h-5 w-5 text-primary align-middle"
                        strokeWidth={2.25}
                      />
                      {data.upcoming.destination ?? "—"}
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {formatDate(data.upcoming.departure_time)}
                      {" · "}
                      {data.upcoming.type === "flight" ? (
                        <AirlineName
                          code={data.upcoming.airline_code}
                          fallback={data.upcoming.carrier}
                        />
                      ) : (
                        data.upcoming.carrier ?? data.upcoming.service_number
                      )}
                    </div>
                  </div>
                  {data.upcoming.service_number ? (
                    <Badge variant="primary">{data.upcoming.service_number}</Badge>
                  ) : null}
                </Link>
              </CardContent>
            </Card>
          ) : null}

          {/* Footprint metric strip — the only totals on this page */}
          <Card
            className="animate-fade-in-up bg-border p-px"
            style={{ animationDelay: "240ms" }}
          >
            <CardContent className="grid grid-cols-2 gap-px sm:grid-cols-4">
              {metrics.map((metric) => (
                <div key={metric.label} className="bg-card p-4">
                  <Stat label={metric.label} value={metric.value} />
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Recent activity */}
          <Card className="animate-fade-in-up" style={{ animationDelay: "360ms" }}>
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
                  <RecordRow key={record.id} record={record} delay={480 + index * 50} />
                ))
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  {t("dashboard.recentEmpty")}
                </p>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
