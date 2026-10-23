"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Bus,
  Plane,
  Plus,
  Trash2,
  TrainFront,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { AirportName } from "@/components/airport-name";
import { FlightStatusBadge, TripStatusBadge } from "@/components/status-badge";
import { TripForm } from "@/components/trip-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type {
  OtherTransport,
  TimelineRecord,
  Train,
  TripDetail,
  TripInput,
  TripItem,
} from "@/lib/types";

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

function isTrainRecord(record: TimelineRecord): record is Train {
  return record.type === "train";
}

function isOtherRecord(record: TimelineRecord): record is OtherTransport {
  return record.type === "other";
}

export default function TripDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t, locale } = useI18n();

  const { data, isLoading } = useQuery({
    queryKey: ["trip", id],
    queryFn: () => api.getTrip(id),
    enabled: Boolean(id),
  });

  const update = useMutation({
    mutationFn: (input: TripInput) => api.updateTrip(id, input),
    onSuccess: (updated) => {
      // Write the server's answer straight into the cache so the header and the
      // edit-diff markers settle immediately instead of waiting on a refetch.
      queryClient.setQueryData<TripDetail>(["trip", id], (prev) =>
        prev ? { ...prev, ...updated } : prev,
      );
      queryClient.invalidateQueries({ queryKey: ["trips"] });
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTrip(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      router.push("/trips");
    },
  });

  const reorder = useMutation({
    mutationFn: (itemIds: string[]) => api.reorderTripItems(id, itemIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trip", id] }),
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

  const start = formatDate(data.start_date, locale);
  const end = formatDate(data.end_date, locale);
  const dates = start && end ? t("trips.dates", { start, end }) : null;

  // Older API responses may not include items yet; fall back to records.
  const items: TripItem[] =
    data.items && data.items.length > 0
      ? data.items
      : data.records.map((record) => ({
          id: record.id,
          item_type: "transport",
          item_id: record.id,
          sort_order: 0,
          start_at: record.departure_time,
          end_at: record.arrival_time,
          record,
        }));
  const displayItems = items.filter(
    (item): item is TripItem & { record: TimelineRecord } => item.record !== null,
  );
  const canReorder = Boolean(data.items && data.items.length > 1);

  const moveItem = (itemId: string, direction: -1 | 1) => {
    const ids = items.map((item) => item.id);
    const index = ids.indexOf(itemId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    reorder.mutate(ids);
  };

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/trips"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("common.back")}
      </Link>

      <div className="flex animate-fade-in-up flex-wrap items-start justify-between gap-4">
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
            {t("trips.records")} · {displayItems.length}
          </h2>
          {reorder.isError ? (
            <p className="text-sm text-danger">{t("trips.reorderFailed")}</p>
          ) : null}
          {displayItems.length === 0 ? (
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
            displayItems.map((item, index) => {
              const record = item.record;
              const itemIndex = items.findIndex((entry) => entry.id === item.id);
              const isTrain = isTrainRecord(record);
              const isOther = isOtherRecord(record);
              const detailHref = isTrain
                ? `/trains/${record.id}`
                : isOther
                  ? `/transports/${record.id}`
                  : `/flights/${record.id}`;
              return (
                <Card
                  key={record.id}
                  interactive
                  className="group animate-fade-in-up"
                  style={{ animationDelay: `${index * 40}ms` }}
                >
                  <CardContent className="flex items-center gap-4 p-4">
                    <Link
                      href={detailHref}
                      className="flex min-w-0 flex-1 items-center gap-4"
                    >
                      {isTrain ? (
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning">
                          <TrainFront className="h-4 w-4" strokeWidth={1.75} />
                        </span>
                      ) : isOther ? (
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning">
                          <Bus className="h-4 w-4" strokeWidth={1.75} />
                        </span>
                      ) : (
                        <AirlineLogo code={record.airline_code} className="h-10 w-10" />
                      )}
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-display text-base font-semibold tracking-tight">
                            {record.origin ? <AirportName value={record.origin} /> : "—"}
                          </span>
                          <ArrowRight className="h-3.5 w-3.5 text-primary transition-transform group-hover:translate-x-0.5" strokeWidth={2.25} />
                          <span className="font-display text-base font-semibold tracking-tight">
                            {record.destination ? <AirportName value={record.destination} /> : "—"}
                          </span>
                          {record.service_number ? (
                            <span className="ml-1 text-xs font-medium text-muted-foreground">
                              {record.service_number}
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-0.5 truncate text-xs text-muted-foreground">
                          {formatDateTime(record.departure_time, locale)}
                          {" · "}
                          {isTrain || isOther ? (
                            record.carrier
                          ) : (
                            <AirlineName code={record.airline_code} fallback={record.carrier} />
                          )}
                          {record.seat ? ` · ${record.seat}` : ""}
                        </div>
                      </div>
                    </Link>
                    {canReorder ? (
                      <div className="flex shrink-0 flex-col">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          disabled={itemIndex <= 0 || reorder.isPending}
                          onClick={() => moveItem(item.id, -1)}
                          title={t("trips.moveUp")}
                          aria-label={t("trips.moveUp")}
                        >
                          <ArrowUp className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          disabled={itemIndex >= items.length - 1 || reorder.isPending}
                          onClick={() => moveItem(item.id, 1)}
                          title={t("trips.moveDown")}
                          aria-label={t("trips.moveDown")}
                        >
                          <ArrowDown className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    ) : null}
                    <FlightStatusBadge status={record.status} />
                  </CardContent>
                </Card>
              );
            })
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
