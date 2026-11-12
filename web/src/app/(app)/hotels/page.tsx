"use client";

import { useQuery } from "@tanstack/react-query";
import { BedDouble, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Fab } from "@/components/ui/fab";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { saveScroll, takeScroll } from "@/lib/scroll-memory";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { usePageTitle } from "@/lib/page-title";

const STATUS_VARIANT: Record<string, "neutral" | "success" | "danger"> = {
  scheduled: "neutral",
  completed: "success",
  cancelled: "danger",
};

function HotelsContent() {
  const { t } = useI18n();
  usePageTitle(t("nav.hotels"));
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["hotels", { search }],
    queryFn: () => api.listHotels({ search: search || undefined, page_size: 100 }),
  });

  // Keep the search term in the URL so it survives the trip to a detail page.
  useEffect(() => {
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    window.history.replaceState(null, "", `/hotels${query}`);
  }, [search]);

  // Coming back from a hotel detail page, restore where the user left off.
  // Next.js scrolls to top on every push navigation, so restore once the list
  // is on screen; the extra frame re-applies after the router's own scroll.
  const scrollRestored = useRef(false);
  useEffect(() => {
    if (scrollRestored.current || !data) return;
    scrollRestored.current = true;
    const y = takeScroll(window.location.pathname + window.location.search);
    if (y === null) return;
    window.scrollTo(0, y);
    requestAnimationFrame(() => window.scrollTo(0, y));
  }, [data]);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("hotels.title")}
        subtitle={
          data ? t("records.total", { count: data.total }) : t("hotels.subtitle")
        }
        actions={
          <Link href="/hotels/new">
            <Button className="hidden md:inline-flex">
              <Plus className="h-4 w-4" />
              {t("hotels.add")}
            </Button>
          </Link>
        }
      />

      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-10"
          placeholder={t("hotels.searchPlaceholder")}
          aria-label={t("common.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
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
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={BedDouble}
          title={t("hotels.empty")}
          hint={t("hotels.emptyHint")}
          action={
            <Link href="/hotels/new">
              <Button variant="outline">
                <Plus className="h-4 w-4" />
                {t("hotels.add")}
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {data.items.map((hotel) => (
            <Link
              key={hotel.id}
              href={`/hotels/${hotel.id}?from=${encodeURIComponent(search ? `/hotels?search=${encodeURIComponent(search)}` : "/hotels")}`}
              onClick={() => saveScroll(window.location.pathname + window.location.search)}
              className="group grid items-center gap-3 border-b border-border bg-card px-4 py-4 last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_7rem] lg:gap-5 lg:px-5"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <BedDouble className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{hotel.hotel}</div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">
                    {hotel.address || "—"}
                  </div>
                </div>
              </div>
              <div className="pl-[3.25rem] text-xs text-muted-foreground lg:pl-0 lg:text-sm">
                {hotel.check_in}
                {hotel.check_out ? ` → ${hotel.check_out}` : ""}
              </div>
              <div className="hidden min-w-0 text-xs text-muted-foreground lg:block">
                {hotel.room_type ? `${hotel.room_type}` : "—"}
                {hotel.room_number ? ` · ${hotel.room_number}` : ""}
              </div>
              <div className="hidden lg:block">
                <Badge variant={STATUS_VARIANT[hotel.status] ?? "neutral"}>
                  {t(`hotels.status.${hotel.status}` as TranslationKey)}
                </Badge>
              </div>
            </Link>
          ))}
        </div>
      )}

      <Fab label={t("hotels.add")} href="/hotels/new">
        <Plus className="h-6 w-6" />
      </Fab>
    </div>
  );
}

export default function HotelsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-5">
          <Skeleton className="h-10 w-56" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      }
    >
      <HotelsContent />
    </Suspense>
  );
}