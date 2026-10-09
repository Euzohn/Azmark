"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Backpack, Plus, Trash2 } from "lucide-react";
import Link from "next/link";

import { TripStatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Trip } from "@/lib/types";

function formatDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
}

export default function TripsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["trips"],
    queryFn: () => api.listTrips(),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteTrip(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trips"] }),
  });

  const handleDelete = (trip: Trip) => {
    if (window.confirm(t("trips.deleteConfirm"))) {
      remove.mutate(trip.id);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">
            {t("trips.title")}
          </h1>
          {data ? (
            <p className="mt-1 text-sm text-muted-foreground">
              {t("trips.total", { count: data.total })}
            </p>
          ) : null}
        </div>
        <Link href="/trips/new">
          <Button>
            <Plus className="h-4 w-4" />
            {t("trips.add")}
          </Button>
        </Link>
      </div>

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }, (_, index) => (
            <Card key={index}>
              <CardContent className="flex flex-col gap-3 p-5">
                <Skeleton className="h-5 w-1/2" />
                <Skeleton className="h-3 w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {data && data.items.length === 0 ? (
        <EmptyState
          icon={Backpack}
          title={t("trips.empty")}
          hint={t("trips.emptyHint")}
          action={
            <Link href="/trips/new">
              <Button variant="outline">
                <Plus className="h-4 w-4" />
                {t("trips.add")}
              </Button>
            </Link>
          }
        />
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        {data?.items.map((trip) => {
          const start = formatDate(trip.start_date);
          const end = formatDate(trip.end_date);
          const dates = start && end ? t("trips.dates", { start, end }) : null;
          return (
            <Card key={trip.id}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <Link
                    href={`/trips/${trip.id}`}
                    className="flex min-w-0 flex-1 items-start gap-3"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
                      <Backpack className="h-5 w-5" strokeWidth={1.75} />
                    </div>
                    <div className="min-w-0">
                      <div className="truncate font-display text-lg font-semibold tracking-tight">
                        {trip.name || "—"}
                      </div>
                      {(trip.origin || trip.destination) && (
                        <div className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
                          {trip.origin}
                          {trip.origin && trip.destination ? (
                            <ArrowRight className="h-3.5 w-3.5 text-primary" strokeWidth={2.25} />
                          ) : null}
                          {trip.destination}
                        </div>
                      )}
                    </div>
                  </Link>
                  <div className="flex shrink-0 items-center gap-1">
                    <TripStatusBadge status={trip.status} />
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(trip)}
                      aria-label={t("common.delete")}
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </div>
                </div>
                {trip.description ? (
                  <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">
                    {trip.description}
                  </p>
                ) : null}
                {dates ? (
                  <p className="mt-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {dates}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
