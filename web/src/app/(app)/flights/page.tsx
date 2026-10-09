"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Plane, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { FlightStatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Flight } from "@/lib/types";

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

export default function FlightsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["flights", search],
    queryFn: () => api.listFlights({ search: search || undefined }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteFlight(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["flights"] }),
  });

  const handleDelete = (flight: Flight) => {
    if (window.confirm(t("flights.deleteConfirm"))) {
      remove.mutate(flight.id);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">
            {t("flights.title")}
          </h1>
          {data ? (
            <p className="mt-1 text-sm text-muted-foreground">
              {t("flights.total", { count: data.total })}
            </p>
          ) : null}
        </div>
        <Link href="/flights/new">
          <Button>
            <Plus className="h-4 w-4" />
            {t("flights.add")}
          </Button>
        </Link>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-10"
          placeholder={t("flights.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }, (_, index) => (
            <Card key={index}>
              <CardContent className="flex items-center gap-4 p-4">
                <Skeleton className="h-11 w-11 shrink-0 rounded-full" />
                <div className="flex flex-1 flex-col gap-2">
                  <Skeleton className="h-5 w-2/5" />
                  <Skeleton className="h-3 w-3/5" />
                </div>
                <Skeleton className="h-6 w-16 rounded-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {data && data.items.length === 0 ? (
        <EmptyState
          icon={Plane}
          title={t("flights.empty")}
          hint={t("flights.emptyHint")}
          action={
            <Link href="/flights/new">
              <Button variant="outline">
                <Plus className="h-4 w-4" />
                {t("flights.add")}
              </Button>
            </Link>
          }
        />
      ) : null}

      <div className="flex flex-col gap-3">
        {data?.items.map((flight) => (
          <Card key={flight.id} className="group">
            <CardContent className="flex items-center gap-4 p-4">
              <Link
                href={`/flights/${flight.id}`}
                className="flex min-w-0 flex-1 items-center gap-4"
              >
                <AirlineLogo code={flight.airline_code} className="h-11 w-11" />
                <div className="min-w-0">
                  <div className="flex items-center gap-2 truncate">
                    <span className="font-display text-lg font-semibold tracking-tight">
                      {flight.origin ?? "—"}
                    </span>
                    <ArrowRight className="h-4 w-4 shrink-0 text-primary" strokeWidth={2.25} />
                    <span className="font-display text-lg font-semibold tracking-tight">
                      {flight.destination ?? "—"}
                    </span>
                    {flight.service_number ? (
                      <span className="ml-1 shrink-0 text-xs font-medium text-muted-foreground">
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
              <div className="flex shrink-0 items-center gap-1">
                <FlightStatusBadge status={flight.status} />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(flight)}
                  aria-label={t("common.delete")}
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground transition-colors group-hover:text-danger" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
