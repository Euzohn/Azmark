"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Backpack, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { TripStatusBadge } from "@/components/status-badge";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Fab } from "@/components/ui/fab";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Trip } from "@/lib/types";

function formatDate(value: string | null, locale: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleDateString(locale, {
        year: "numeric",
        month: "short",
        day: "numeric",
        timeZone: "UTC",
      });
}

export default function TripsPage() {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<Trip | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["trips"],
    queryFn: () => api.listTrips(),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteTrip(id),
    onSuccess: () => {
      setPendingDelete(null);
      void queryClient.invalidateQueries({ queryKey: ["trips"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("trips.title")}
        subtitle={data ? t("trips.total", { count: data.total }) : undefined}
        actions={
          <Link href="/trips/new">
            <Button className="hidden md:inline-flex">
              <Plus className="h-4 w-4" />
              {t("trips.add")}
            </Button>
          </Link>
        }
      />

      {isError ? <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-danger/30 bg-card p-5"><span className="text-sm text-danger">{t("common.error")}</span><Button variant="outline" onClick={() => void refetch()}>{t("common.retry")}</Button></div> : null}

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

      {data && !isError && data.items.length === 0 ? (
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
          const start = formatDate(trip.start_date, locale);
          const end = formatDate(trip.end_date, locale);
          const dates = start && end ? t("trips.dates", { start, end }) : null;
          return (
            <Card
              key={trip.id}
              interactive
              className="overflow-hidden"
            >
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <Link
                    href={`/trips/${trip.id}`}
                    className="flex min-w-0 flex-1 items-start gap-3"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-primary">
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
                      onClick={() => { remove.reset(); setPendingDelete(trip); }}
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

      <Dialog open={pendingDelete !== null} onClose={() => { if (!remove.isPending) setPendingDelete(null); }} title={t("common.confirmDelete")} variant="responsive">
        <p className="text-sm text-muted-foreground">{t("trips.deleteConfirm")}</p>
        {remove.isError ? <p role="alert" className="mt-3 text-sm text-danger">{t("common.error")}</p> : null}
        <div className="mt-6 flex justify-end gap-3"><Button variant="outline" disabled={remove.isPending} onClick={() => setPendingDelete(null)}>{t("common.cancel")}</Button><Button variant="danger" disabled={remove.isPending} onClick={() => { if (pendingDelete) remove.mutate(pendingDelete.id); }}>{t(remove.isPending ? "common.loading" : "common.delete")}</Button></div>
      </Dialog>

      <Fab label={t("trips.add")} href="/trips/new">
        <Plus className="h-6 w-6" />
      </Fab>
    </div>
  );
}
