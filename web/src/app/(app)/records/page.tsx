"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Backpack,
  Bus,
  History,
  List as ListIcon,
  Plane,
  Plus,
  Search,
  SlidersHorizontal,
  TrainFront,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { AirlineLogo } from "@/components/airline-logo";
import { AirportName } from "@/components/airport-name";
import { FlightStatusBadge } from "@/components/status-badge";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { DateInput } from "@/components/ui/date-input";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type {
  Flight,
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

type ViewMode = "list" | "timeline";

function formatDateTime(value: string | null, locale: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString(locale, {
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

/** TimelineRecord is a union keyed by a `string` (not a literal), so TS won't
 *  narrow on `record.type === "flight"`. Access the flight-only field safely. */
function airlineCode(record: TimelineRecord): string | null {
  return record.type === "flight" ? (record as Flight).airline_code : null;
}

function parseType(value: string | null): RecordType | "" {
  if (value === "flight" || value === "train" || value === "other") {
    return value;
  }
  return "";
}

function parseView(value: string | null): ViewMode {
  return value === "timeline" ? "timeline" : "list";
}

function dayKey(value: string | null): string {
  if (!value) return "unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function dateLabel(key: string, locale: string): string {
  if (key === "unknown") return "—";
  const date = new Date(key);
  if (Number.isNaN(date.getTime())) return key;
  return date.toLocaleDateString(locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
  });
}

function matchesSearch(record: TimelineRecord, search: string): boolean {
  if (!search) return true;
  const needle = search.toLowerCase();
  return [
    record.origin,
    record.destination,
    record.service_number,
    record.carrier,
    airlineCode(record),
  ]
    .filter((v): v is string => Boolean(v))
    .some((v) => v.toLowerCase().includes(needle));
}

function RecordCard({
  record,
  index = 0,
  tripName,
}: {
  record: TimelineRecord;
  index?: number;
  tripName?: string;
}) {
  const { t, locale } = useI18n();
  const typeKey = TYPE_KEYS[record.type] ?? "records.type.other";
  const Icon = TYPE_ICONS[record.type as keyof typeof TYPE_ICONS] ?? Bus;

  return (
    <Card interactive className="group animate-fade-in-up" style={{ animationDelay: `${index * 30}ms` }}>
      <CardContent className="flex items-center gap-4 p-4">
        <Link href={recordHref(record)} className="flex min-w-0 flex-1 items-center gap-4">
          {record.type === "flight" ? (
            <AirlineLogo code={airlineCode(record)} className="h-11 w-11" />
          ) : (
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
              <Icon className="h-5 w-5" />
            </div>
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2 truncate">
              {record.origin ? (
                <span className="font-display text-lg font-semibold tracking-tight">
                  <AirportName value={record.origin} />
                </span>
              ) : (
                <span className="font-display text-lg font-semibold tracking-tight">—</span>
              )}
              <ArrowRight
                className="h-4 w-4 shrink-0 text-primary transition-transform group-hover:translate-x-0.5"
                strokeWidth={2.25}
              />
              {record.destination ? (
                <span className="font-display text-lg font-semibold tracking-tight">
                  <AirportName value={record.destination} />
                </span>
              ) : (
                <span className="font-display text-lg font-semibold tracking-tight">—</span>
              )}
              {record.service_number ? (
                <span className="ml-1 shrink-0 text-xs font-medium text-muted-foreground">
                  {record.service_number}
                </span>
              ) : null}
            </div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {formatDateTime(record.departure_time, locale)}
              {record.arrival_time
                ? ` → ${formatDateTime(record.arrival_time, locale)}`
                : ""}
              {record.carrier ? ` · ${record.carrier}` : ""}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Badge>{t(typeKey)}</Badge>
              {tripName ? (
                <Badge variant="primary" className="max-w-[14rem]">
                  <Backpack className="h-3 w-3 shrink-0" />
                  <span className="truncate">{tripName}</span>
                </Badge>
              ) : null}
            </div>
          </div>
        </Link>
        <div className="flex shrink-0 items-center gap-1">
          <FlightStatusBadge status={record.status} />
        </div>
      </CardContent>
    </Card>
  );
}

function RecordsContent() {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const [view, setView] = useState<ViewMode>(() => parseView(searchParams.get("view")));
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<RecordType | "">(() =>
    parseType(searchParams.get("type")),
  );
  const [statusFilter, setStatusFilter] = useState("");
  const [tripFilter, setTripFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<RecordSort>("newest");
  const [page, setPage] = useState(1);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

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
    enabled: view === "list",
  });

  const { data: timeline, isLoading: timelineLoading } = useQuery({
    queryKey: ["timeline"],
    queryFn: api.getTimeline,
    enabled: view === "timeline",
  });

  const tripNames = new Map<string, string>(
    (trips?.items ?? []).map((trip) => [trip.id, trip.name] as const),
  );
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));
  const hasFilters = Boolean(
    search || typeFilter || statusFilter || tripFilter || dateFrom || dateTo,
  );
  const advancedCount = [statusFilter, tripFilter, dateFrom, dateTo].filter(Boolean).length;

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

  const timelineGroups = useMemo(() => {
    const items = (timeline ?? []).filter((record) => {
      if (typeFilter && record.type !== typeFilter) return false;
      if (statusFilter && record.status !== statusFilter) return false;
      if (tripFilter && record.trip_id !== tripFilter) return false;
      const key = dayKey(record.departure_time);
      if (dateFrom && (key === "unknown" || key < dateFrom)) return false;
      if (dateTo && (key === "unknown" || key > dateTo)) return false;
      return matchesSearch(record, search);
    });
    items.sort((a, b) => {
      const ta = a.departure_time ? new Date(a.departure_time).getTime() : 0;
      const tb = b.departure_time ? new Date(b.departure_time).getTime() : 0;
      return tb - ta;
    });
    const map = new Map<string, TimelineRecord[]>();
    for (const record of items) {
      const key = dayKey(record.departure_time);
      const bucket = map.get(key);
      if (bucket) bucket.push(record);
      else map.set(key, [record]);
    }
    return Array.from(map.entries());
  }, [timeline, typeFilter, statusFilter, tripFilter, dateFrom, dateTo, search]);

  const timelineCount = timelineGroups.reduce((sum, [, records]) => sum + records.length, 0);
  const shownTotal = view === "timeline" ? timelineCount : data?.total;
  const totalLabel =
    shownTotal !== undefined
      ? `${t("records.subtitle")} · ${t("records.total", { count: shownTotal })}`
      : t("records.subtitle");

  const addOptions = [
    { href: "/flights/new", label: t("records.addFlight"), icon: Plane },
    { href: "/trains/new", label: t("records.addTrain"), icon: TrainFront },
    { href: "/transports/new", label: t("records.addTransport"), icon: Bus },
  ];

  const addActions = (
    <>
      <div className="hidden flex-wrap items-center gap-2 sm:flex">
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
      <Button
        size="sm"
        className="sm:hidden"
        aria-haspopup="dialog"
        onClick={() => setAddOpen(true)}
      >
        <Plus className="h-4 w-4" />
        {t("records.add")}
      </Button>
    </>
  );

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("records.title")} subtitle={totalLabel} actions={addActions} />

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-10"
              placeholder={t("records.searchPlaceholder")}
              value={search}
              onChange={(event) => change(setSearch, event.target.value)}
            />
          </div>
          <Segmented
            value={view}
            onChange={(value) => {
              setView(value);
              setPage(1);
            }}
            options={[
              { value: "list", label: t("records.view.list"), icon: ListIcon },
              { value: "timeline", label: t("records.view.timeline"), icon: History },
            ]}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={typeFilter}
            onChange={(event) => change(setTypeFilter, event.target.value as RecordType | "")}
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

          {view === "list" ? (
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
          ) : null}

          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-expanded={advancedOpen || advancedCount > 0}
            aria-controls="records-advanced-filters"
            onClick={() => setAdvancedOpen((open) => !open)}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            {t("records.filter.more")}
            {advancedCount > 0 ? (
              <span className="rounded-full bg-accent px-1.5 text-[10px] leading-4 text-accent-foreground">
                {advancedCount}
              </span>
            ) : null}
          </Button>

          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={resetFilters}>
              <X className="h-3.5 w-3.5" />
              {t("records.filter.reset")}
            </Button>
          ) : null}
        </div>

        {advancedOpen || advancedCount > 0 ? (
          <div
            id="records-advanced-filters"
            className="grid gap-3 rounded-xl border border-border bg-card/60 p-3 sm:grid-cols-2 lg:grid-cols-4"
          >
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                {t("records.filter.status")}
              </span>
              <Select
                value={statusFilter}
                onChange={(event) => change(setStatusFilter, event.target.value)}
                className="w-full text-sm"
              >
                <option value="">{t("records.filter.all")}</option>
                <option value="scheduled">{t("flights.status.scheduled")}</option>
                <option value="completed">{t("flights.status.completed")}</option>
                <option value="cancelled">{t("flights.status.cancelled")}</option>
              </Select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                {t("records.filter.trip")}
              </span>
              <Select
                value={tripFilter}
                onChange={(event) => change(setTripFilter, event.target.value)}
                className="w-full text-sm"
              >
                <option value="">{t("records.filter.all")}</option>
                {trips?.items.map((trip) => (
                  <option key={trip.id} value={trip.id}>
                    {trip.name}
                  </option>
                ))}
              </Select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                {t("records.filter.dateFrom")}
              </span>
              <DateInput
                value={dateFrom}
                onChange={(event) => change(setDateFrom, event.target.value)}
                className="w-full text-sm"
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                {t("records.filter.dateTo")}
              </span>
              <DateInput
                value={dateTo}
                onChange={(event) => change(setDateTo, event.target.value)}
                className="w-full text-sm"
              />
            </label>
          </div>
        ) : null}
      </div>

      {view === "list" ? (
        <ListView
          isLoading={isLoading}
          isEmpty={Boolean(data && data.items.length === 0)}
          items={data?.items ?? []}
          tripNames={tripNames}
          page={page}
          pages={pages}
          onPage={setPage}
        />
      ) : (
        <TimelineView
          isLoading={timelineLoading}
          groups={timelineGroups}
          isEmpty={timelineGroups.length === 0}
          tripNames={tripNames}
        />
      )}

      <BottomSheet open={addOpen} onClose={() => setAddOpen(false)} title={t("records.add")}>
        <div className="flex flex-col gap-1">
          {addOptions.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setAddOpen(false)}
              className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-foreground transition-colors hover:bg-accent"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-accent-foreground">
                <Icon className="h-4 w-4" />
              </span>
              {label}
            </Link>
          ))}
        </div>
      </BottomSheet>
    </div>
  );
}

interface ListViewProps {
  isLoading: boolean;
  isEmpty: boolean;
  items: TimelineRecord[];
  tripNames: Map<string, string>;
  page: number;
  pages: number;
  onPage: (page: number) => void;
}

function ListView({ isLoading, isEmpty, items, tripNames, page, pages, onPage }: ListViewProps) {
  const { t } = useI18n();

  if (isLoading) {
    return (
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
    );
  }

  if (isEmpty) {
    return (
      <EmptyState
        icon={ListIcon}
        title={t("records.empty")}
        hint={t("records.emptyHint")}
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <Link href="/flights/new">
              <Button variant="outline">
                <Plane className="h-4 w-4" />
                {t("records.addFlight")}
              </Button>
            </Link>
            <Link href="/trains/new">
              <Button variant="outline">
                <TrainFront className="h-4 w-4" />
                {t("records.addTrain")}
              </Button>
            </Link>
            <Link href="/transports/new">
              <Button variant="outline">
                <Bus className="h-4 w-4" />
                {t("records.addTransport")}
              </Button>
            </Link>
          </div>
        }
      />
    );
  }

  return (
    <>
      <div className="flex flex-col gap-3">
        {items.map((record, index) => (
          <RecordCard
            key={record.id}
            record={record}
            index={index}
            tripName={record.trip_id ? tripNames.get(record.trip_id) : undefined}
          />
        ))}
      </div>

      {pages > 1 ? (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPage(Math.max(1, page - 1))}
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
            onClick={() => onPage(Math.min(pages, page + 1))}
          >
            {t("common.next")}
          </Button>
        </div>
      ) : null}
    </>
  );
}

interface TimelineViewProps {
  isLoading: boolean;
  isEmpty: boolean;
  groups: Array<[string, TimelineRecord[]]>;
  tripNames: Map<string, string>;
}

function TimelineView({ isLoading, isEmpty, groups, tripNames }: TimelineViewProps) {
  const { t, locale } = useI18n();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-5">
        {Array.from({ length: 3 }, (_, index) => (
          <div key={index} className="flex flex-col gap-3">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (isEmpty) {
    return (
      <EmptyState
        icon={History}
        title={t("timeline.empty")}
        hint={t("timeline.emptyHint")}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {groups.map(([key, records], groupIndex) => (
        <section key={key} className="flex flex-col gap-3 animate-fade-in-up" style={{ animationDelay: `${groupIndex * 40}ms` }}>
          <div className="flex items-center gap-3">
            <span className="h-2 w-2 rounded-full bg-primary/70" />
            <h2 className="font-display text-sm font-semibold tracking-tight text-muted-foreground">
              {dateLabel(key, locale)}
            </h2>
            <span className="text-xs text-muted-foreground/60">· {records.length}</span>
            <div className="h-px flex-1 bg-border" />
          </div>
          <div className="flex flex-col gap-3 sm:border-l sm:border-border sm:pl-5">
            {records.map((record, index) => (
              <RecordCard
                key={record.id}
                record={record}
                index={index}
                tripName={record.trip_id ? tripNames.get(record.trip_id) : undefined}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export default function RecordsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-5">
          <Skeleton className="h-10 w-56" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      }
    >
      <RecordsContent />
    </Suspense>
  );
}
