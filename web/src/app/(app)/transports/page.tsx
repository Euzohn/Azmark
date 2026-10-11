"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Bus, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { OtherTransport } from "@/lib/types";

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

function vehicleLabel(value: string | null): TranslationKey | null {
  if (!value) return null;
  const map: Record<string, TranslationKey> = {
    bus: "transports.vehicleType.bus",
    ferry: "transports.vehicleType.ferry",
    taxi: "transports.vehicleType.taxi",
    rideshare: "transports.vehicleType.rideshare",
    car: "transports.vehicleType.car",
    bike: "transports.vehicleType.bike",
    walk: "transports.vehicleType.walk",
    cruise: "transports.vehicleType.cruise",
    other: "transports.vehicleType.other",
  };
  return map[value] ?? null;
}

export default function TransportsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["transports", search],
    queryFn: () => api.listOtherTransports({ search: search || undefined }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteOtherTransport(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["transports"] }),
  });

  const handleDelete = (transport: OtherTransport) => {
    if (window.confirm(t("transports.deleteConfirm"))) {
      remove.mutate(transport.id);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">
            {t("transports.title")}
          </h1>
          {data ? (
            <p className="mt-1 text-sm text-muted-foreground">
              {t("transports.total", { count: data.total })}
            </p>
          ) : null}
        </div>
        <Link href="/transports/new">
          <Button>
            <Plus className="h-4 w-4" />
            {t("transports.add")}
          </Button>
        </Link>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-10"
          placeholder={t("transports.searchPlaceholder")}
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
          icon={Bus}
          title={t("transports.empty")}
          hint={t("transports.emptyHint")}
          action={
            <Link href="/transports/new">
              <Button variant="outline">
                <Plus className="h-4 w-4" />
                {t("transports.add")}
              </Button>
            </Link>
          }
        />
      ) : null}

      <div className="flex flex-col gap-3">
        {data?.items.map((transport) => (
          <Card key={transport.id} className="group">
            <CardContent className="flex items-center gap-4 p-4">
              <Link
                href={`/transports/${transport.id}`}
                className="flex min-w-0 flex-1 items-center gap-4"
              >
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent text-muted-foreground">
                  <Bus className="h-5 w-5" strokeWidth={1.75} />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 truncate">
                    <span className="font-display text-lg font-semibold tracking-tight">
                      {transport.origin ?? "—"}
                    </span>
                    <ArrowRight className="h-4 w-4 shrink-0 text-primary" strokeWidth={2.25} />
                    <span className="font-display text-lg font-semibold tracking-tight">
                      {transport.destination ?? "—"}
                    </span>
                    {transport.service_number ? (
                      <span className="ml-1 shrink-0 text-xs font-medium text-muted-foreground">
                        {transport.service_number}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
                    <span className="truncate">
                      {formatDateTime(transport.departure_time)}
                      {transport.carrier ? ` · ${transport.carrier}` : ""}
                    </span>
                    {vehicleLabel(transport.vehicle_type) ? (
                      <span className="shrink-0">· {t(vehicleLabel(transport.vehicle_type)!)}</span>
                    ) : null}
                    {transport.seat ? <span className="shrink-0">· {transport.seat}</span> : null}
                  </div>
                </div>
              </Link>
              <div className="flex shrink-0 items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(transport)}
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