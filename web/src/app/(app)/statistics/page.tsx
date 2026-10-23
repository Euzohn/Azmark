"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, CalendarRange, ChevronDown, ChevronUp, Compass } from "lucide-react";
import { useMemo, useState } from "react";

import { AirlineLogo } from "@/components/airline-logo";
import { AirlineName } from "@/components/airline-name";
import { AirportName } from "@/components/airport-name";
import { ColumnChart, DonutChart, type ChartDatum } from "@/components/charts";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Stat } from "@/components/ui/stat";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { BreakdownItem, StatisticsRead } from "@/lib/types";

const FLIGHT_CABIN_KEYS: Record<string, TranslationKey> = {
  economy: "flights.cabin.economy",
  premium_economy: "flights.cabin.premium_economy",
  business: "flights.cabin.business",
  first: "flights.cabin.first",
};

const TRAIN_CLASS_KEYS: Record<string, TranslationKey> = {
  business: "trains.cabin.business",
  first: "trains.cabin.first",
  second: "trains.cabin.second",
  premium_soft: "trains.cabin.premium_soft",
  hard: "trains.cabin.hard",
  hard_seat: "trains.cabin.hard_seat",
  soft_seat: "trains.cabin.soft_seat",
};

const SEAT_TYPE_KEYS: Record<string, TranslationKey> = {
  window: "trains.seatType.window",
  aisle: "trains.seatType.aisle",
  middle: "trains.seatType.middle",
  sleeper: "trains.seatType.sleeper",
  reclining: "trains.seatType.reclining",
  standing: "trains.seatType.standing",
};

const TRAIN_TYPE_KEYS: Record<string, TranslationKey> = {
  high_speed: "trains.trainType.high_speed",
  intercity: "trains.trainType.intercity",
  conventional: "trains.trainType.conventional",
  night: "trains.trainType.night",
};

const ALLIANCE_KEYS: Record<string, TranslationKey> = {
  star_alliance: "alliance.star_alliance",
  skyteam: "alliance.skyteam",
  oneworld: "alliance.oneworld",
};

const VISIBLE_ROWS = 8;

function translateLabel(
  map: Record<string, TranslationKey>,
  label: string,
  t: (key: TranslationKey) => string,
): string {
  const key = map[label];
  return key ? t(key) : label;
}

function share(value: number, total: number): string {
  return `${Math.round((value / Math.max(total, 1)) * 100)}%`;
}

interface BarListProps {
  items: BreakdownItem[];
  total: number;
  renderLeading?: (item: BreakdownItem) => React.ReactNode;
  renderLabel?: (item: BreakdownItem) => React.ReactNode;
  formatLabel?: (label: string) => string;
}

function BarList({ items, total, renderLeading, renderLabel, formatLabel }: BarListProps) {
  const max = Math.max(1, ...items.map((item) => item.count));

  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          {renderLeading ? <div className="shrink-0">{renderLeading(item)}</div> : null}
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-sm font-medium">
                {renderLabel ? (
                  renderLabel(item)
                ) : formatLabel ? (
                  formatLabel(item.label)
                ) : (
                  item.label
                )}
                {item.name && !renderLabel && !formatLabel ? (
                  <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                    {item.name}
                  </span>
                ) : null}
              </span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                <span className="font-medium text-foreground">{item.count}</span>
                <span className="ml-1.5 text-[10px]">{share(item.count, total)}</span>
              </span>
            </div>
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary to-[#96670c] transition-all duration-500"
                style={{ width: `${(item.count / max) * 100}%` }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

interface StatsSection {
  key: string;
  title: string;
  items: BreakdownItem[];
  kind?: "airline" | "airport";
  formatLabel?: (label: string) => string;
}

function BreakdownCard({ section, delay }: { section: StatsSection; delay: number }) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const total = section.items.reduce((sum, item) => sum + item.count, 0);
  const visible = expanded ? section.items : section.items.slice(0, VISIBLE_ROWS);

  return (
    <Card className="animate-fade-in-up" style={{ animationDelay: `${delay}ms` }}>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <CardTitle>{section.title}</CardTitle>
        {section.items.length > VISIBLE_ROWS ? (
          <Button variant="ghost" size="sm" onClick={() => setExpanded((value) => !value)}>
            {expanded ? t("stats.showLess") : t("stats.showAll", { count: section.items.length })}
            {expanded ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent>
        <BarList
          items={visible}
          total={total}
          formatLabel={section.formatLabel}
          renderLeading={
            section.kind === "airline"
              ? (item) => <AirlineLogo code={item.label} className="h-8 w-8" />
              : undefined
          }
          renderLabel={
            section.kind === "airline"
              ? (item) => <AirlineName code={item.label} fallback={item.name} />
              : section.kind === "airport"
                ? (item) => <AirportName value={item.label} />
                : undefined
          }
        />
      </CardContent>
    </Card>
  );
}

function monthLabel(locale: string) {
  const formatter = new Intl.DateTimeFormat(locale, { month: "short" });
  return (label: string) => {
    const [, month] = label.split("-").map(Number);
    return formatter.format(new Date(2024, month - 1, 1));
  };
}

function buildSection(
  data: StatisticsRead | undefined,
  t: (key: TranslationKey) => string,
  translate: (map: Record<string, TranslationKey>) => (label: string) => string,
): { flight: StatsSection[]; train: StatsSection[]; time: StatsSection[] } {
  if (!data) return { flight: [], train: [], time: [] };

  return {
    flight: [
      { key: "airline", title: t("stats.byAirline"), items: data.by_airline, kind: "airline" },
      { key: "aircraft", title: t("stats.byAircraft"), items: data.by_aircraft },
      { key: "airport", title: t("stats.byAirport"), items: data.by_airport, kind: "airport" },
      {
        key: "cabin",
        title: t("stats.byCabin"),
        items: data.by_cabin,
        formatLabel: translate(FLIGHT_CABIN_KEYS),
      },
      {
        key: "seat-type",
        title: t("stats.bySeatType"),
        items: data.by_seat_type,
        formatLabel: translate(SEAT_TYPE_KEYS),
      },
      {
        key: "alliance",
        title: t("stats.byAlliance"),
        items: data.by_alliance,
        formatLabel: translate(ALLIANCE_KEYS),
      },
    ],
    train: [
      { key: "operator", title: t("stats.byTrainOperator"), items: data.by_train_operator },
      {
        key: "train-type",
        title: t("stats.byTrainType"),
        items: data.by_train_type,
        formatLabel: translate(TRAIN_TYPE_KEYS),
      },
      { key: "station", title: t("stats.byStation"), items: data.by_station },
      {
        key: "train-class",
        title: t("stats.byTrainClass"),
        items: data.by_train_class,
        formatLabel: translate(TRAIN_CLASS_KEYS),
      },
      {
        key: "train-seat-type",
        title: t("stats.byTrainSeatType"),
        items: data.by_train_seat_type,
        formatLabel: translate(SEAT_TYPE_KEYS),
      },
    ],
    time: [{ key: "day", title: t("stats.byDay"), items: [...data.by_day].reverse() }],
  };
}

export default function StatisticsPage() {
  const { t, locale } = useI18n();
  const [selectedYear, setSelectedYear] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["statistics"],
    queryFn: api.getStatistics,
  });

  const translate = (map: Record<string, TranslationKey>) => (label: string) =>
    translateLabel(map, label, t);

  const sections = useMemo(
    () => buildSection(data, t, translate),
    // `t` and `translate` are recreated per render; data + locale drive content.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data, locale],
  );

  const years = useMemo(
    () => Array.from(new Set((data?.by_month ?? []).map((item) => item.label.slice(0, 4)))).sort(),
    [data],
  );
  const monthCounts = useMemo(
    () => new Map((data?.by_month ?? []).map((item) => [item.label, item.count])),
    [data],
  );
  const activeYear = selectedYear && years.includes(selectedYear) ? selectedYear : years.at(-1);
  const monthData: ChartDatum[] = activeYear
    ? Array.from({ length: 12 }, (_, index) => {
        const key = `${activeYear}-${String(index + 1).padStart(2, "0")}`;
        return { label: key, value: monthCounts.get(key) ?? 0 };
      })
    : [];

  const totals = data?.totals;
  const journeys = (totals?.flights ?? 0) + (totals?.trains ?? 0) + (totals?.transports ?? 0);

  const summary = [
    { label: t("dashboard.stats.countries"), value: totals?.countries ?? 0 },
    { label: t("dashboard.stats.cities"), value: totals?.cities ?? 0 },
    { label: t("dashboard.stats.journeys"), value: journeys },
    {
      label: t("dashboard.stats.distance"),
      value: `${Math.round(totals?.distance_km ?? 0).toLocaleString(locale)} ${t("stats.km")}`,
    },
    { label: t("dashboard.stats.trips"), value: totals?.trips ?? 0 },
  ];

  const mix: ChartDatum[] = [
    { label: t("stats.group.flight"), value: totals?.flights ?? 0 },
    { label: t("stats.group.train"), value: totals?.trains ?? 0 },
    { label: t("stats.other"), value: totals?.transports ?? 0 },
  ];

  const cabin: ChartDatum[] = (data?.by_cabin ?? []).map((item) => ({
    label: translate(FLIGHT_CABIN_KEYS)(item.label),
    value: item.count,
  }));
  const alliance: ChartDatum[] = (data?.by_alliance ?? []).map((item) => ({
    label: translate(ALLIANCE_KEYS)(item.label),
    value: item.count,
  }));

  const groups = [
    { key: "flight", title: t("stats.group.flight"), sections: sections.flight },
    { key: "train", title: t("stats.group.train"), sections: sections.train },
    { key: "time", title: t("stats.group.time"), sections: sections.time },
  ]
    .map((group) => ({
      ...group,
      sections: group.sections.filter((section) => section.items.length > 0),
    }))
    .filter((group) => group.sections.length > 0);

  const hasRecords = Boolean(data && journeys > 0);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("stats.title")} subtitle={t("stats.subtitle")} />

      {isLoading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-24 w-full" />
          <div className="grid gap-4 md:grid-cols-2">
            {Array.from({ length: 4 }, (_, index) => (
              <Skeleton key={index} className="h-48 w-full" />
            ))}
          </div>
        </div>
      ) : null}

      {data && !hasRecords ? (
        <EmptyState icon={BarChart3} title={t("stats.empty")} hint={t("stats.emptyHint")} />
      ) : null}

      {data && hasRecords ? (
        <>
          <Card className="animate-fade-in-up">
            <CardHeader className="flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <Compass className="h-4 w-4 text-primary" />
                <CardTitle>{t("stats.summary")}</CardTitle>
              </div>
              <span className="text-xs text-muted-foreground">
                {t("stats.sinceFirst", { year: data.by_year[0]?.label ?? "—" })}
              </span>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3 lg:grid-cols-5">
                {summary.map((item) => (
                  <Stat key={item.label} label={item.label} value={item.value} />
                ))}
              </div>
            </CardContent>
          </Card>

          {groups.length > 1 ? (
            <nav className="flex flex-wrap gap-2" aria-label={t("stats.jumpTo")}>
              {groups.map((group) => (
                <a
                  key={group.key}
                  href={`#stats-${group.key}`}
                  className="rounded-full border border-border bg-card px-3.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                >
                  {group.title}
                </a>
              ))}
            </nav>
          ) : null}

          <section id="stats-activity" className="flex scroll-mt-24 flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {t("stats.activity")}
              </h2>
              <span className="text-xs text-muted-foreground">
                {t("stats.activityHint")}
              </span>
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              <Card className="animate-fade-in-up lg:col-span-2">
                <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
                  <CardTitle>{t("stats.monthly")}</CardTitle>
                  {years.length > 1 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {[...years].reverse().map((year) => (
                        <button
                          key={year}
                          type="button"
                          onClick={() => setSelectedYear(year)}
                          className={
                            year === activeYear
                              ? "rounded-full bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground"
                              : "rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                          }
                        >
                          {year}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs tabular-nums text-muted-foreground">{activeYear}</span>
                  )}
                </CardHeader>
                <CardContent>
                  <ColumnChart
                    data={monthData}
                    ariaLabel={t("stats.monthly")}
                    formatLabel={monthLabel(locale)}
                  />
                </CardContent>
              </Card>

              <Card className="animate-fade-in-up" style={{ animationDelay: "60ms" }}>
                <CardHeader className="flex-row items-center justify-between">
                  <CardTitle>{t("stats.yearly")}</CardTitle>
                  <CalendarRange className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <ColumnChart
                    data={data.by_year.map((item) => ({ label: item.label, value: item.count }))}
                    ariaLabel={t("stats.yearly")}
                    height={132}
                  />
                </CardContent>
              </Card>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Card className="animate-fade-in-up">
              <CardHeader>
                <CardTitle>{t("stats.mix")}</CardTitle>
              </CardHeader>
              <CardContent>
                <DonutChart
                  data={mix}
                  ariaLabel={t("stats.mix")}
                  centerLabel={t("dashboard.stats.journeys")}
                />
              </CardContent>
            </Card>

            {cabin.length > 1 ? (
              <Card className="animate-fade-in-up">
                <CardHeader>
                  <CardTitle>{t("stats.cabinMix")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <DonutChart
                    data={cabin}
                    ariaLabel={t("stats.cabinMix")}
                    centerLabel={t("dashboard.stats.flights")}
                  />
                </CardContent>
              </Card>
            ) : null}

            {alliance.length > 1 ? (
              <Card className="animate-fade-in-up">
                <CardHeader>
                  <CardTitle>{t("stats.allianceMix")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <DonutChart
                    data={alliance}
                    ariaLabel={t("stats.allianceMix")}
                    centerLabel={t("dashboard.stats.flights")}
                  />
                </CardContent>
              </Card>
            ) : null}
          </section>

          {groups.map((group) => (
            <section
              key={group.key}
              id={`stats-${group.key}`}
              className="flex scroll-mt-24 flex-col gap-3"
            >
              <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {group.title}
              </h2>
              <div className="grid gap-4 md:grid-cols-2">
                {group.sections.map((section, index) => (
                  <BreakdownCard
                    key={section.key}
                    section={section}
                    delay={Math.min(index * 40, 160)}
                  />
                ))}
              </div>
            </section>
          ))}
        </>
      ) : null}
    </div>
  );
}
