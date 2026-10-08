"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Backpack, Plus, Trash2 } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Trip } from "@/lib/types";

const STATUS_KEYS: Record<string, TranslationKey> = {
  planned: "trips.status.planned",
  ongoing: "trips.status.ongoing",
  completed: "trips.status.completed",
};

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
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{t("trips.title")}</h1>
          {data ? (
            <p className="text-xs text-muted-foreground">
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
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }, (_, index) => (
            <Card key={index}>
              <CardContent className="flex items-center gap-3 p-4">
                <Skeleton className="h-5 w-5 shrink-0 rounded-full" />
                <div className="flex flex-1 flex-col gap-2">
                  <Skeleton className="h-4 w-2/5" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
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

      <div className="flex flex-col gap-3">
        {data?.items.map((trip) => {
          const start = formatDate(trip.start_date);
          const end = formatDate(trip.end_date);
          const dates = start && end ? t("trips.dates", { start, end }) : null;
          return (
            <Card key={trip.id}>
              <CardContent className="flex items-center justify-between gap-3 p-4">
                <Link
                  href={`/trips/${trip.id}`}
                  className="flex min-w-0 flex-1 items-center gap-3"
                >
                  <Backpack className="h-5 w-5 shrink-0 text-primary" />
                  <div className="min-w-0">
                    <div className="truncate font-medium">
                      {trip.origin ?? ""}
                      {trip.origin && trip.destination ? " → " : ""}
                      {trip.destination ?? ""}
                      {trip.name ? ` · ${trip.name}` : ""}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {dates || t(STATUS_KEYS[trip.status] ?? "trips.status.planned")}
                    </div>
                  </div>
                </Link>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(trip)}
                  aria-label={t("common.delete")}
                >
                  <Trash2 className="h-4 w-4 text-danger" />
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
