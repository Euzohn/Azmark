"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Bus,
  List as ListIcon,
  Plane,
  Plus,
  Search,
  TrainFront,
  X,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { FlightStatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type {
  RecordFilters,
  RecordSort,
  RecordType,
  TimelineRecord,
} from "@/lib/types";

const PAGE_SIZE = 20;

const TYPE_KEYS: Record<string, TranslationKey> = {
  flight: "records.type.flight",
  train: "records.type.train",
  other: "records.type.other",
};

const TYPE_ICONS = {
  flight: Plane,
  train: TrainFront,
  other: Bus,
} as const;

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

function recordHref(record: TimelineRecord): string {
  if (record.type === "train") return `/trains/${record.id}`;
  if (record.type === "other") return `/transports/${record.id}`;
  return `/flights/${record.id}`;
}

export default function RecordsPage() {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<RecordType | "">("");
  const [statusFilter, setStatusFilter] = useState("");
  const [tripFilter, setTripFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<RecordSort>("newest");
  const [page, setPage] = useState(1);

  const filters: RecordFilters = {
    search: search || undefined,
    type: typeFilter || undefined,
    status: statusFilter || undefined,
    trip_id: tripFilter || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    sort,
    page,
    page_size: PAGE_SIZE,
  };

  const { data: trips } = useQuery({
    queryKey: ["trips", { page_size: 100 }],
    queryFn: () => api.listTrips({ page_size: 100 }),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["records", filters],
    queryFn: () => api.listRecords(filters),
  });

  const tripNames = new Map<string, string>(
    (trips?.items ?? []).map((trip) => [trip.id, trip.name] as const),
  );
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));
  const hasFilters = Boolean(
    search || typeFilter || statusFilter || tripFilter || dateFrom || dateTo,
  );

  const change = <T,>(setter: (value: T) => void, value: T) => {
    setter(value);
    setPage(1);
  };

  const resetFilters = () => {
    setSearch("");
    setTypeFilter("");
    setStatusFilter("");
    setTripFilter("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight animate-fade-in-up">
            {t("records.title")}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {data
              ? `${t("records.subtitle")} · ${t("records.total", { count: data.total })}`
              : t("records.subtitle")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link href="/flights/new">
            <Button variant="outline" size="sm">
              <Plane className="h-4 w-4" />
              {t("records.addFlight")}
            </Button>
          </Link>
          <Link href="/trains/new">
            <Button variant="outline" size="sm">
              <TrainFront className="h-4 w-4" />
              {t("records.addTrain")}
            </Button>
          </Link>
          <Link href="/transports/new">
            <Button size="sm">
              <Plus className="h-4 w-4" />
              {t("records.addTransport")}
            </Button>
          </Link>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-10"
            placeholder={t("records.searchPlaceholder")}
            value={search}
            onChange={(event) => change(setSearch, event.target.value)}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={typeFilter}
            onChange={(event) =>
              change(setTypeFilter, event.target.value as RecordType | "")
            }
            className="w-auto text-sm"
            aria-label={t("records.filter.type")}
          >
            <option value="">
              {t("records.filter.type")}: {t("records.filter.all")}
            </option>
            <option value="flight">{t("records.type.flight")}</option>
            <option value="train">{t("records.type.train")}</option>
            <option value="other">{t("records.type.other")}</option>
          </Select>

          <Select
            value={statusFilter}
            onChange={(event) => change(setStatusFilter, event.target.value)}
            className="w-auto text-sm"
            aria-label={t("records.filter.status")}
          >
            <option value="">
              {t("records.filter.status")}: {t("records.filter.all")}
            </option>
            <option value="scheduled">{t("flights.status.scheduled")}</option>
            <option value="completed">{t("flights.status.completed")}</option>
            <option value="cancelled">{t("flights.status.cancelled")}</option>
          </Select>

          <Select
            value={tripFilter}
            onChange={(event) => change(setTripFilter, event.target.value)}
            className="w-auto text-sm"
            aria-label={t("records.filter.trip")}
          >
            <option value="">
              {t("records.filter.trip")}: {t("records.filter.all")}
            </option>
            {trips?.items.map((trip) => (
              <option key={trip.id} value={trip.id}>
                {trip.name}
              </option>
            ))}
          </Select>

          <Select
            value={sort}
            onChange={(event) => change(setSort, event.target.value as RecordSort)}
            className="w-auto text-sm"
            aria-label={t("records.filter.sort")}
          >
            <option value="newest">{t("records.sort.newest")}</option>
            <option value="oldest">{t("records.sort.oldest")}</option>
            <option value="departure">{t("records.sort.departure")}</option>
            <option value="arrival">{t("records.sort.arrival")}</option>
            <option value="created">{t("records.sort.created")}</option>
          </Select>

          <Input
            type="date"
            value={dateFrom}
            onChange={(event) => change(setDateFrom, event.target.value)}
            className="w-auto text-sm"
            aria-label={t("records.filter.dateFrom")}
          />
          <Input
            type="date"
            value={dateTo}
            onChange={(event) => change(setDateTo, event.target.value)}
            className="w-auto text-sm"
            aria-label={t("records.filter.dateTo")}
          />

          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={resetFilters}>
              <X className="h-3.5 w-3.5" />
              {t("records.filter.reset")}
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
          icon={ListIcon}
          title={t("records.empty")}
          hint={t("records.emptyHint")}
          action={
            <Link href="/flights/new">
              <Button variant="outline">
                <Plus className="h-4 w-4" />
                {t("records.addFlight")}
              </Button>
            </Link>
          }
        />
      ) : null}

      <div className="flex flex-col gap-3">
        {data?.items.map((record, index) => {
          const typeKey = TYPE_KEYS[record.type] ?? "records.type.other";
          const Icon = TYPE_ICONS[record.type as keyof typeof TYPE_ICONS] ?? Bus;
          const tripName = record.trip_id ? tripNames.get(record.trip_id) : undefined;

          return (
            <Card
              key={record.id}
              interactive
              className="group animate-fade-in-up"
              style={{ animationDelay: `${index * 30}ms` }}
            >
              <CardContent className="flex items-center gap-4 p-4">
                <Link
                  href={recordHref(record)}
                  className="flex min-w-0 flex-1 items-center gap-4"
                >
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 truncate">
                      <span className="font-display text-lg font-semibold tracking-tight">
                        {record.origin ?? "—"}
                      </span>
                      <ArrowRight
                        className="h-4 w-4 shrink-0 text-primary transition-transform group-hover:translate-x-0.5"
                        strokeWidth={2.25}
                      />
                      <span className="font-display text-lg font-semibold tracking-tight">
                        {record.destination ?? "—"}
                      </span>
                      {record.service_number ? (
                        <span className="ml-1 shrink-0 text-xs font-medium text-muted-foreground">
                          {record.service_number}
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-0.5 truncate text-xs text-muted-foreground">
                      {formatDateTime(record.departure_time)}
                      {record.arrival_time
                        ? ` → ${formatDateTime(record.arrival_time)}`
                        : ""}
                      {record.carrier ? ` · ${record.carrier}` : ""}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <Badge>{t(typeKey)}</Badge>
                      {tripName ? <Badge variant="primary">{tripName}</Badge> : null}
                    </div>
                  </div>
                </Link>
                <div className="flex shrink-0 items-center gap-1">
                  <FlightStatusBadge status={record.status} />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {data && data.total > PAGE_SIZE ? (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            {t("common.previous")}
          </Button>
          <span className="text-sm text-muted-foreground">
            {t("common.pageOf", { page, pages })}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => setPage((current) => Math.min(pages, current + 1))}
          >
            {t("common.next")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
