"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Plane, Plus, Search, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { AllianceBadge } from "@/components/alliance-badge";
import { FlightStatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Flight, FlightFilters } from "@/lib/types";

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

function cabinLabel(value: string | null): TranslationKey | null {
  if (!value) return null;
  switch (value) {
    case "economy":
      return "flights.cabin.economy";
    case "premium_economy":
      return "flights.cabin.premium_economy";
    case "business":
      return "flights.cabin.business";
    case "first":
      return "flights.cabin.first";
    default:
      return null;
  }
}

export default function FlightsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [cabinFilter, setCabinFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [tripFilter, setTripFilter] = useState("");

  const filters: FlightFilters = {
    search: search || undefined,
    status: statusFilter || undefined,
    cabin_class: cabinFilter || undefined,
    trip_id: tripFilter || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  };

  const { data: trips } = useQuery({
    queryKey: ["trips"],
    queryFn: () => api.listTrips(),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["flights", filters],
    queryFn: () => api.listFlights(filters),
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

  const hasFilters = Boolean(
    statusFilter || cabinFilter || tripFilter || dateFrom || dateTo,
  );

  const resetFilters = () => {
    setStatusFilter("");
    setCabinFilter("");
    setTripFilter("");
    setDateFrom("");
    setDateTo("");
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

      <div className="flex flex-col gap-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-10"
            placeholder={t("flights.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-auto text-sm"
          >
            <option value="">{t("flights.filter.status")}: {t("flights.filter.all")}</option>
            <option value="scheduled">{t("flights.status.scheduled")}</option>
            <option value="completed">{t("flights.status.completed")}</option>
            <option value="cancelled">{t("flights.status.cancelled")}</option>
          </Select>
          <Select
            value={cabinFilter}
            onChange={(e) => setCabinFilter(e.target.value)}
            className="w-auto text-sm"
          >
            <option value="">{t("flights.filter.cabinClass")}: {t("flights.filter.all")}</option>
            <option value="economy">{t("flights.cabin.economy")}</option>
            <option value="premium_economy">{t("flights.cabin.premium_economy")}</option>
            <option value="business">{t("flights.cabin.business")}</option>
            <option value="first">{t("flights.cabin.first")}</option>
          </Select>
          <Select
            value={tripFilter}
            onChange={(e) => setTripFilter(e.target.value)}
            className="w-auto text-sm"
          >
            <option value="">{t("flights.filter.trip")}: {t("flights.filter.all")}</option>
            {trips?.items.map((trip) => (
              <option key={trip.id} value={trip.id}>
                {trip.name || `${trip.origin ?? ""} → ${trip.destination ?? ""}`}
              </option>
            ))}
          </Select>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="w-auto text-sm"
            placeholder={t("flights.filter.dateFrom")}
          />
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="w-auto text-sm"
            placeholder={t("flights.filter.dateTo")}
          />
          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={resetFilters}>
              <X className="h-3.5 w-3.5" />
              {t("flights.filter.reset")}
            </Button>
          ) : null}
        </div>
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
                  <div className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
                    <span className="truncate">
                      {formatDateTime(flight.departure_time)}
                      {" · "}
                      <AirlineName code={flight.airline_code} fallback={flight.carrier} />
                    </span>
                    {flight.seat ? <span className="shrink-0">· {flight.seat}</span> : null}
                    {cabinLabel(flight.cabin_class) ? (
                      <span className="shrink-0">· {t(cabinLabel(flight.cabin_class)!)}</span>
                    ) : null}
                  </div>
                  {flight.airline_code ? (
                    <div className="mt-1">
                      <AllianceBadge code={flight.airline_code} />
                    </div>
                  ) : null}
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
