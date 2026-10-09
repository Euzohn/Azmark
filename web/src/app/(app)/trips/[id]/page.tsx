"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Plane, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { FlightStatusBadge, TripStatusBadge } from "@/components/status-badge";
import { TripForm } from "@/components/trip-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TripInput } from "@/lib/types";

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
}

export default function TripDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data, isLoading } = useQuery({
    queryKey: ["trip", id],
    queryFn: () => api.getTrip(id),
    enabled: Boolean(id),
  });

  const update = useMutation({
    mutationFn: (input: TripInput) => api.updateTrip(id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      queryClient.invalidateQueries({ queryKey: ["trip", id] });
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTrip(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      router.push("/trips");
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-2/5" />
        <Skeleton className="h-4 w-1/3" />
      </div>
    );
  }
  if (!data) {
    return <p className="text-sm text-muted-foreground">{t("common.empty")}</p>;
  }

  const start = formatDate(data.start_date);
  const end = formatDate(data.end_date);
  const dates = start && end ? t("trips.dates", { start, end }) : null;

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/trips"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("common.back")}
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-display text-3xl font-semibold tracking-tight">{data.name}</h1>
            <TripStatusBadge status={data.status} />
          </div>
          {(data.origin || data.destination) && (
            <div className="mt-1.5 flex items-center gap-1.5 text-sm text-muted-foreground">
              {data.origin}
              {data.origin && data.destination ? (
                <ArrowRight className="h-4 w-4 text-primary" strokeWidth={2.25} />
              ) : null}
              {data.destination}
            </div>
          )}
          {dates ? (
            <p className="mt-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {dates}
            </p>
          ) : null}
          {data.description ? (
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">{data.description}</p>
          ) : null}
        </div>
        <Button
          variant="danger"
          size="sm"
          onClick={() => {
            if (window.confirm(t("trips.deleteConfirm"))) {
              remove.mutate();
            }
          }}
        >
          <Trash2 className="h-4 w-4" />
          {t("common.delete")}
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            {t("trips.flights")} · {data.flights.length}
          </h2>
          {data.flights.length === 0 ? (
            <EmptyState
              icon={Plane}
              title={t("trips.noFlights")}
              hint={t("trips.noFlightsHint")}
              action={
                <Link href="/flights/new">
                  <Button variant="outline">
                    <Plus className="h-4 w-4" />
                    {t("flights.add")}
                  </Button>
                </Link>
              }
            />
          ) : (
            data.flights.map((flight) => (
              <Card key={flight.id}>
                <CardContent className="flex items-center gap-4 p-4">
                  <Link
                    href={`/flights/${flight.id}`}
                    className="flex min-w-0 flex-1 items-center gap-4"
                  >
                    <AirlineLogo code={flight.airline_code} className="h-10 w-10" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-display text-base font-semibold tracking-tight">
                          {flight.origin ?? "—"}
                        </span>
                        <ArrowRight className="h-3.5 w-3.5 text-primary" strokeWidth={2.25} />
                        <span className="font-display text-base font-semibold tracking-tight">
                          {flight.destination ?? "—"}
                        </span>
                        {flight.service_number ? (
                          <span className="ml-1 text-xs font-medium text-muted-foreground">
                            {flight.service_number}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-0.5 truncate text-xs text-muted-foreground">
                        {formatDateTime(flight.departure_time)}
                        {" · "}
                        <AirlineName code={flight.airline_code} fallback={flight.carrier} />
                        {flight.seat ? ` · ${flight.seat}` : ""}
                      </div>
                    </div>
                  </Link>
                  <FlightStatusBadge status={flight.status} />
                </CardContent>
              </Card>
            ))
          )}
        </div>

        <Card className="self-start">
          <CardContent className="p-5">
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              {t("trips.edit")}
            </h2>
            <TripForm
              initial={data}
              submitting={update.isPending}
              onSubmit={(input) => update.mutate(input)}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
