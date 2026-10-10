"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, History, TrainFront } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { FlightStatusBadge } from "@/components/status-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TimelineRecord, Train } from "@/lib/types";

function dayKey(value: string | null): string {
  if (!value) return "unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function timeLabel(value: string | null): string {
  if (!value) return "--:--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function isTrainRecord(record: TimelineRecord): record is Train {
  return record.type === "train";
}

function dateLabel(key: string): string {
  if (key === "unknown") return "—";
  const date = new Date(key);
  if (Number.isNaN(date.getTime())) return key;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
  });
}

export default function TimelinePage() {
  const { t } = useI18n();

  const { data, isLoading } = useQuery({
    queryKey: ["timeline"],
    queryFn: api.getTimeline,
  });

  const groups = useMemo(() => {
    const map = new Map<string, TimelineRecord[]>();
    for (const record of data ?? []) {
      const key = dayKey(record.departure_time);
      const bucket = map.get(key);
      if (bucket) bucket.push(record);
      else map.set(key, [record]);
    }
    return Array.from(map.entries());
  }, [data]);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          {t("timeline.title")}
        </h1>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-4">
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-20 w-full" />
          ))}
        </div>
      ) : null}

      {!isLoading && groups.length === 0 ? (
        <EmptyState
          icon={History}
          title={t("timeline.empty")}
          hint={t("timeline.emptyHint")}
        />
      ) : null}

      {!isLoading && groups.length > 0 ? (
        <div className="flex flex-col gap-8">
          {groups.map(([key, records]) => (
            <div key={key} className="flex flex-col gap-3">
              <div className="font-display text-sm font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                {dateLabel(key)}
              </div>
              <div className="relative flex flex-col gap-2 border-l border-border pl-5">
                {records.map((record) => (
                  <div key={record.id} className="relative">
                    <span className="absolute -left-[26px] top-4 h-2.5 w-2.5 rounded-full border-2 border-background bg-primary" />
                    <Link
                      href={isTrainRecord(record) ? `/trains/${record.id}` : `/flights/${record.id}`}
                      className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 shadow-[0_1px_3px_rgba(33,26,18,0.06)] transition-colors hover:border-primary/40"
                    >
                      <span className="w-11 shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
                        {timeLabel(record.departure_time)}
                      </span>
                      {isTrainRecord(record) ? (
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-muted-foreground">
                          <TrainFront className="h-4 w-4" strokeWidth={1.75} />
                        </span>
                      ) : (
                        <AirlineLogo code={record.airline_code} className="h-9 w-9" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 truncate text-sm font-medium">
                          <span>{record.origin ?? "—"}</span>
                          <ArrowRight
                            className="h-3.5 w-3.5 shrink-0 text-primary"
                            strokeWidth={2.5}
                          />
                          <span>{record.destination ?? "—"}</span>
                          {record.service_number ? (
                            <span className="ml-1 shrink-0 text-xs font-normal text-muted-foreground">
                              {record.service_number}
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-0.5 truncate text-xs text-muted-foreground">
                          {isTrainRecord(record) ? (
                            record.carrier
                          ) : (
                            <AirlineName code={record.airline_code} fallback={record.carrier} />
                          )}
                        </div>
                      </div>
                      <FlightStatusBadge status={record.status} />
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
