"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plane, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { AirlineName } from "@/components/airline-name";
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
      <div className="flex flex-col gap-3">
        <Skeleton className="h-5 w-2/5" />
        <Skeleton className="h-4 w-1/3" />
      </div>
    );
  }
  if (!data) {
    return <p className="text-sm text-muted-foreground">{t("common.empty")}</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <Link
        href="/trips"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("common.back")}
      </Link>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{data.name}</h1>
          {data.origin || data.destination ? (
            <p className="text-xs text-muted-foreground">
              {[data.origin, data.destination].filter(Boolean).join(" → ")}
            </p>
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

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t("trips.flights")} ({data.flights.length})
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
                <CardContent className="p-4">
                  <Link
                    href={`/flights/${flight.id}`}
                    className="flex min-w-0 items-center gap-3"
                  >
                    <Plane className="h-5 w-5 shrink-0 text-primary" />
                    <div className="min-w-0">
                      <div className="truncate font-medium">
                        {flight.origin ?? "—"} → {flight.destination ?? "—"}
                        {flight.service_number ? ` · ${flight.service_number}` : ""}
                      </div>
                      <div className="truncate text-xs text-muted-foreground">
                        {formatDateTime(flight.departure_time)}
                        {" · "}
                        <AirlineName code={flight.airline_code} fallback={flight.carrier} />
                        {flight.seat ? ` · ${flight.seat}` : ""}
                      </div>
                    </div>
                  </Link>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        <Card>
          <CardContent className="flex flex-col gap-4 p-4">
            <h2 className="text-sm font-medium text-muted-foreground">{t("trips.edit")}</h2>
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
