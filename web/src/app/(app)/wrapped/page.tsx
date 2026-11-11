"use client";

import { useQuery } from "@tanstack/react-query";
import { Gift, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { WrappedRead } from "@/lib/types";

function monthShort(locale: string): Intl.DateTimeFormat {
  return new Intl.DateTimeFormat(locale, { month: "short" });
}

function TopList({
  title,
  items,
}: {
  title: string;
  items: { label: string; name?: string | null; count: number }[];
}) {
  if (items.length === 0) return null;
  const max = items[0]?.count ?? 1;
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          <div className="w-28 shrink-0 truncate text-sm">{item.name ?? item.label}</div>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary/70"
              style={{ width: `${(item.count / max) * 100}%` }}
            />
          </div>
          <div className="w-8 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
            {item.count}
          </div>
        </div>
      ))}
    </div>
  );
}

function Chapter({ children }: { children: React.ReactNode }) {
  return (
    <section className="min-h-[52vh] py-8 first:pt-2">
      <Card className="flex min-h-[44vh] flex-col justify-center border-border/70 bg-card/60 p-8">
        <CardContent className="flex flex-col gap-6 px-0 py-0">{children}</CardContent>
      </Card>
    </section>
  );
}

function BigNumber({ value, unit }: { value: string | number; unit?: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-5xl font-bold tabular-nums tracking-tight sm:text-6xl">{value}</span>
      {unit ? <span className="text-lg text-muted-foreground">{unit}</span> : null}
    </div>
  );
}

function WrappedContent() {
  const { t, locale } = useI18n();
  const [yearParam] = useState(() => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("year");
  });
  const [selectedYear, setSelectedYear] = useState<number | null>(
    yearParam && !Number.isNaN(Number(yearParam)) ? Number(yearParam) : null,
  );
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["wrapped", selectedYear ?? "latest"],
    queryFn: () => api.getWrapped(selectedYear ?? undefined),
  });

  // Reflect the chosen year in the URL so the page can be shared/bookmarked.
  useEffect(() => {
    if (!data) return;
    const url = new URL(window.location.href);
    url.searchParams.set("year", String(data.year));
    window.history.replaceState(null, "", url.toString());
  }, [data]);

  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const months = useMemo(() => monthShort(locale), [locale]);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-[60vh] w-full rounded-3xl" />
      </div>
    );
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="flex items-center justify-between gap-3 rounded-xl border border-danger/30 bg-card p-5"
      >
        <span className="text-sm text-danger">{t("common.error")}</span>
        <Button variant="outline" onClick={() => void refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }

  const wrapped: WrappedRead | undefined = data;
  if (!wrapped || (wrapped.available_years.length === 0 && wrapped.totals.travel_days === 0)) {
    return (
      <EmptyState icon={Gift} title={t("wrapped.empty")} hint={t("wrapped.emptyHint")} />
    );
  }

  const totals = wrapped.totals;
  const journeys = totals.flights + totals.trains + totals.transports;
  const spend = wrapped.spend;

  const scrollChapter = (direction: 1 | -1) => {
    const container = scrollRef.current;
    if (!container) return;
    const chapters = Array.from(container.querySelectorAll<HTMLElement>("section"));
    if (chapters.length === 0) return;
    // The chapter occupying the viewport centre is the one the reader is on.
    const mid = window.innerHeight / 2;
    let current = 0;
    chapters.forEach((chapter, index) => {
      if (chapter.getBoundingClientRect().top <= mid) current = index;
    });
    const target = Math.max(0, Math.min(chapters.length - 1, current + direction));
    chapters[target]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const fmtDate = (iso: string) => {
    const [year, month, day] = iso.split("-").map(Number);
    return new Date(year, (month ?? 1) - 1, day ?? 1).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("wrapped.title")}
        subtitle={t("wrapped.subtitle", { year: wrapped.year })}
        actions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 rounded-full border border-border p-1">
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7"
                aria-label={t("common.previous")}
                onClick={() => scrollChapter(-1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7"
                aria-label={t("common.next")}
                onClick={() => scrollChapter(1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
            {wrapped.available_years.length > 1 ? (
              <Select
                className="h-9 w-auto text-sm"
                value={String(wrapped.year)}
                onChange={(event) => setSelectedYear(Number(event.target.value))}
                aria-label={t("wrapped.title")}
              >
                {wrapped.available_years.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </Select>
            ) : null}
          </div>
        }
      />

      <div ref={scrollRef}>
        <Chapter>
          <div className="flex flex-col items-center gap-3 text-center">
            <p className="text-sm uppercase tracking-widest text-muted-foreground">
              {wrapped.year}
            </p>
            <BigNumber value={numbers.format(journeys)} unit={t("wrapped.journeysLabel")} />
            <p className="text-sm text-muted-foreground">
              {t("wrapped.distance", { value: numbers.format(Math.round(totals.distance_km)) })}
            </p>
            {wrapped.first_journey && wrapped.last_journey ? (
              <p className="text-xs text-muted-foreground">
                {t("wrapped.firstJourney", { date: fmtDate(wrapped.first_journey) })} ·{" "}
                {t("wrapped.lastJourney", { date: fmtDate(wrapped.last_journey) })}
              </p>
            ) : null}
          </div>
        </Chapter>

        <Chapter>
          <h2 className="text-lg font-semibold">{t("wrapped.footprint")}</h2>
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-3">
            <div>
              <BigNumber value={totals.countries} />
              <p className="mt-1 text-xs text-muted-foreground">{t("wrapped.countries")}</p>
            </div>
            <div>
              <BigNumber value={totals.cities} />
              <p className="mt-1 text-xs text-muted-foreground">{t("wrapped.cities")}</p>
            </div>
            <div>
              <BigNumber value={totals.travel_days} />
              <p className="mt-1 text-xs text-muted-foreground">{t("wrapped.travelDays")}</p>
            </div>
          </div>
        </Chapter>

        <Chapter>
          <h2 className="text-lg font-semibold">{t("wrapped.moves")}</h2>
          <div className="grid grid-cols-3 gap-6">
            <div>
              <BigNumber value={totals.flights} />
              <p className="mt-1 text-xs text-muted-foreground">{t("wrapped.flights")}</p>
            </div>
            <div>
              <BigNumber value={totals.trains} />
              <p className="mt-1 text-xs text-muted-foreground">{t("wrapped.trains")}</p>
            </div>
            <div>
              <BigNumber value={totals.transports} />
              <p className="mt-1 text-xs text-muted-foreground">{t("wrapped.transports")}</p>
            </div>
          </div>
          <TopList title={t("wrapped.topAirlines")} items={wrapped.top_airlines} />
          <TopList title={t("wrapped.topAirports")} items={wrapped.top_airports} />
          <TopList title={t("wrapped.topStations")} items={wrapped.top_stations} />
          <TopList title={t("wrapped.topAircraft")} items={wrapped.top_aircraft} />
        </Chapter>

        {wrapped.most_visited_city || wrapped.favorite_trip ? (
          <Chapter>
            <h2 className="text-lg font-semibold">{t("wrapped.favorites")}</h2>
            <div className="grid gap-6 sm:grid-cols-2">
              {wrapped.most_visited_city ? (
                <div className="rounded-xl border border-border/60 p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    {t("wrapped.mostVisitedCity")}
                  </p>
                  <p className="mt-1 text-2xl font-semibold">
                    {locale === "zh-CN"
                      ? (wrapped.most_visited_city.name ?? wrapped.most_visited_city.label)
                      : wrapped.most_visited_city.label}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("wrapped.visits", { count: wrapped.most_visited_city.count })}
                  </p>
                </div>
              ) : null}
              {wrapped.favorite_trip ? (
                <div className="rounded-xl border border-border/60 p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    {t("wrapped.favoriteTrip")}
                  </p>
                  <p className="mt-1 truncate text-2xl font-semibold">
                    {wrapped.favorite_trip.name ?? wrapped.favorite_trip.label}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("wrapped.journeysCount", { count: wrapped.favorite_trip.count })}
                  </p>
                </div>
              ) : null}
            </div>
          </Chapter>
        ) : null}

        {wrapped.longest_route ? (
          <Chapter>
            <h2 className="text-lg font-semibold">{t("wrapped.longest")}</h2>
            <div className="flex flex-col gap-2">
              <p className="text-2xl font-semibold">
                {wrapped.longest_route.origin.code}{" "}
                <span className="text-muted-foreground">→</span>{" "}
                {wrapped.longest_route.destination.code}
              </p>
              <p className="text-sm text-muted-foreground">
                {numbers.format(Math.round(wrapped.longest_route.distance_km))} {t("stats.km")}
                {wrapped.longest_route.carrier ? ` · ${wrapped.longest_route.carrier}` : ""}
                {wrapped.longest_route.service_number
                  ? ` · ${wrapped.longest_route.service_number}`
                  : ""}
              </p>
            </div>
          </Chapter>
        ) : null}

        <Chapter>
          <h2 className="text-lg font-semibold">{t("wrapped.trips")}</h2>
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            <div>
              <BigNumber value={totals.trips} />
              <p className="mt-1 text-xs text-muted-foreground">{t("wrapped.trips")}</p>
            </div>
            <div>
              <BigNumber value={totals.hotels} />
              <p className="mt-1 text-xs text-muted-foreground">
                {t("wrapped.hotels")} · {t("wrapped.nights", { count: totals.hotel_nights })}
              </p>
            </div>
            <div>
              <BigNumber value={totals.activities} />
              <p className="mt-1 text-xs text-muted-foreground">{t("wrapped.activities")}</p>
            </div>
          </div>
        </Chapter>

        {spend.converted_count > 0 || spend.unconverted_count > 0 ? (
          <Chapter>
            <h2 className="text-lg font-semibold">{t("wrapped.spend")}</h2>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold tabular-nums">
                {numbers.format(Number(spend.converted_total))}
              </span>
              <span className="text-lg text-muted-foreground">{spend.report_currency}</span>
            </div>
            {spend.unconverted.length > 0 ? (
              <p className="text-xs text-muted-foreground">
                {t("wrapped.spendUnconverted", {
                  count: spend.unconverted_count,
                  items: spend.unconverted
                    .map((bucket) => `${numbers.format(Number(bucket.amount))} ${bucket.currency}`)
                    .join(" · "),
                })}
              </p>
            ) : null}
          </Chapter>
        ) : null}

        {wrapped.by_month.length > 0 ? (
          <Chapter>
            <h2 className="text-lg font-semibold">{t("stats.group.time")}</h2>
            <div className="grid grid-cols-4 gap-3 sm:grid-cols-6">
              {wrapped.by_month.map((item) => {
                const [yearValue, monthValue] = item.label.split("-");
                const date = new Date(Number(yearValue), Number(monthValue) - 1, 1);
                return (
                  <div
                    key={item.label}
                    className="flex flex-col items-center gap-1 rounded-xl border border-border/60 p-3"
                  >
                    <span className="text-xs uppercase text-muted-foreground">
                      {months.format(date)}
                    </span>
                    <span className="text-lg font-semibold tabular-nums">{item.count}</span>
                  </div>
                );
              })}
            </div>
          </Chapter>
        ) : null}

        <div className="flex justify-center py-6">
          <Link
            href="/statistics"
            className="inline-flex h-9 items-center justify-center rounded-md border border-border px-4 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            {t("wrapped.back")}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function WrappedPage() {
  return (
    <Suspense fallback={<Skeleton className="h-[60vh] w-full rounded-3xl" />}>
      <WrappedContent />
    </Suspense>
  );
}
