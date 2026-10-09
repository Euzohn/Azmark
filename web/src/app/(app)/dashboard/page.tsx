"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Backpack,
  Compass,
  Globe2,
  MapPin,
  Plane,
  PlaneTakeoff,
  Route,
  TrainFront,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { FlightStatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Flight } from "@/lib/types";

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

function StatTile({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
          <Icon className="h-5 w-5" strokeWidth={1.75} />
        </div>
        <div className="min-w-0">
          <div className="font-display text-2xl font-semibold leading-none tracking-tight">
            {value}
          </div>
          <div className="mt-1 truncate text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function RecordRow({ flight }: { flight: Flight }) {
  return (
    <Link
      href={`/flights/${flight.id}`}
      className="flex items-center gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-accent/50"
    >
      <AirlineLogo code={flight.airline_code} className="h-9 w-9" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 truncate text-sm font-medium">
          <span>{flight.origin ?? "—"}</span>
          <ArrowRight className="h-3.5 w-3.5 shrink-0 text-primary" strokeWidth={2.5} />
          <span>{flight.destination ?? "—"}</span>
          {flight.service_number ? (
            <span className="ml-1 shrink-0 text-xs font-normal text-muted-foreground">
              {flight.service_number}
            </span>
          ) : null}
        </div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">
          {formatDate(flight.departure_time)}
        </div>
      </div>
      <FlightStatusBadge status={flight.status} />
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

  const statTiles: { icon: LucideIcon; key: TranslationKey; value: string | number }[] = [
    { icon: Globe2, key: "dashboard.stats.countries", value: stats?.countries ?? 0 },
    { icon: MapPin, key: "dashboard.stats.cities", value: stats?.cities ?? 0 },
    { icon: Route, key: "dashboard.stats.journeys", value: stats?.journeys ?? 0 },
    {
      icon: Compass,
      key: "dashboard.stats.distance",
      value: `${Math.round(stats?.distance_km ?? 0).toLocaleString()} km`,
    },
    { icon: Plane, key: "dashboard.stats.flights", value: stats?.flights ?? 0 },
    { icon: TrainFront, key: "dashboard.stats.trains", value: stats?.trains ?? 0 },
    { icon: Backpack, key: "dashboard.stats.trips", value: stats?.trips ?? 0 },
  ];

  const hasRecords = (stats?.journeys ?? 0) > 0;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          {name ? t("dashboard.greeting", { name }) : t("dashboard.title")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("app.tagline")}</p>
      </div>

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <Card key={index}>
              <CardContent className="p-4">
                <Skeleton className="h-11 w-full" />
              </CardContent>
            </Card>
          ))}
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
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {statTiles.map((tile) => (
              <StatTile
                key={tile.key}
                icon={tile.icon}
                label={t(tile.key)}
                value={tile.value}
              />
            ))}
          </div>

          {data?.upcoming ? (
            <Card className="overflow-hidden">
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <PlaneTakeoff className="h-4 w-4 text-primary" />
                  {t("dashboard.upcoming")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Link
                  href={`/flights/${data.upcoming.id}`}
                  className="flex items-center gap-4"
                >
                  <AirlineLogo code={data.upcoming.airline_code} className="h-12 w-12" />
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
                      <AirlineName
                        code={data.upcoming.airline_code}
                        fallback={data.upcoming.carrier}
                      />
                    </div>
                  </div>
                  <Badge variant="primary">{data.upcoming.service_number ?? ""}</Badge>
                </Link>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>{t("dashboard.recent")}</CardTitle>
              <Link href="/flights">
                <Button variant="ghost" size="sm">
                  {t("dashboard.viewAll")}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent className="flex flex-col gap-1">
              {data && data.recent.length > 0 ? (
                data.recent.map((flight) => <RecordRow key={flight.id} flight={flight} />)
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
