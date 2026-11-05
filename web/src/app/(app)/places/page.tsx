"use client";

import { useQuery } from "@tanstack/react-query";
import { MapPin, Plus, Search } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Fab } from "@/components/ui/fab";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { PlaceType } from "@/lib/types";

const TYPES: PlaceType[] = [
  "airport",
  "train_station",
  "bus_station",
  "port",
  "hotel",
  "restaurant",
  "attraction",
  "city",
  "place",
  "other",
];

function PlacesContent() {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [type, setType] = useState<PlaceType | "">("");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["places", { search, type }],
    queryFn: () =>
      api.listPlaces({
        search: search || undefined,
        type: type || undefined,
        page_size: 100,
      }),
  });

  useEffect(() => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    if (type) query.set("type", type);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    window.history.replaceState(null, "", `/places${suffix}`);
  }, [search, type]);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("places.title")}
        subtitle={data ? t("records.total", { count: data.total }) : t("places.subtitle")}
        actions={
          <Link href="/places/new">
            <Button className="hidden md:inline-flex">
              <Plus className="h-4 w-4" />
              {t("places.add")}
            </Button>
          </Link>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-10"
            placeholder={t("places.searchPlaceholder")}
            aria-label={t("common.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          aria-label={t("places.type")}
          value={type}
          onChange={(e) => setType(e.target.value as PlaceType | "")}
          className="sm:w-48"
        >
          <option value="">{t("places.filterAll")}</option>
          {TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`places.type.${value}`)}
            </option>
          ))}
        </Select>
      </div>

      {isError ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-4 rounded-xl border border-danger/30 bg-card p-5"
        >
          <p className="text-sm text-danger">{t("common.error")}</p>
          <Button variant="outline" onClick={() => void refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      ) : isLoading ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={MapPin}
          title={t("places.empty")}
          hint={t("places.emptyHint")}
          action={
            <Link href="/places/new">
              <Button variant="outline">
                <Plus className="h-4 w-4" />
                {t("places.add")}
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {data.items.map((place) => (
            <Link
              key={place.id}
              href={`/places/${place.id}`}
              className="group flex items-center gap-4 border-b border-border bg-card px-4 py-4 last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:px-5"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <MapPin className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{place.name}</div>
                <div className="mt-1 truncate text-xs text-muted-foreground">
                  {[place.localized_name, place.city, place.country]
                    .filter(Boolean)
                    .join(" · ") || t("places.location")}
                </div>
              </div>
              <Badge variant="neutral">{t(`places.type.${place.type}`)}</Badge>
            </Link>
          ))}
        </div>
      )}

      <Fab label={t("places.add")} href="/places/new">
        <Plus className="h-6 w-6" />
      </Fab>
    </div>
  );
}

export default function PlacesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-5">
          <Skeleton className="h-10 w-56" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-20 w-full rounded-xl" />
          <Skeleton className="h-20 w-full rounded-xl" />
        </div>
      }
    >
      <PlacesContent />
    </Suspense>
  );
}
