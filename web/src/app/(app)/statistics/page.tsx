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
  新时速: "trains.trainType.x",
  高铁: "trains.trainType.g",
  动车300: "trains.trainType.t",
  动车250: "trains.trainType.k",
  动力集中: "trains.trainType.d",
  城际: "trains.trainType.c",
  市郊: "trains.trainType.s",
  快速160: "trains.trainType.z",
  快速140: "trains.trainType.n",
  普速: "trains.trainType.v",
  旅游: "trains.trainType.y",
  // Legacy enum values created before the 2026 revision.
  high_speed: "trains.trainType.g",
  intercity: "trains.trainType.c",
  conventional: "trains.trainType.v",
  night: "trains.trainType.y",
};

const ALLIANCE_KEYS: Record<string, TranslationKey> = {
  star_alliance: "alliance.star_alliance",
  skyteam: "alliance.skyteam",
  oneworld: "alliance.oneworld",
};

const EXPENSE_CATEGORY_KEYS: Record<string, TranslationKey> = {
  transport: "expenses.category.transport",
  accommodation: "expenses.category.accommodation",
  food: "expenses.category.food",
  shopping: "expenses.category.shopping",
  entertainment: "expenses.category.entertainment",
  other: "expenses.category.other",
};

const EXPENSE_SOURCE_KEYS: Record<string, TranslationKey> = {
  transport: "stats.source.transport",
  hotel: "stats.source.hotel",
  activity: "stats.source.activity",
  manual: "stats.source.manual",
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

/** Locale-aware money, always with the ISO code so currencies stay unambiguous. */
function money(value: number | string, currency: string, locale: string): string {
  const amount = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(amount)) return `${value} ${currency}`;
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      currencyDisplay: "code",
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString(locale)} ${currency}`;
  }
}

/** Bare amount in the report currency — used where the currency is already labelled. */
function amountFull(value: number, locale: string): string {
  if (!Number.isFinite(value)) return "—";
  try {
    return new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value);
  } catch {
    return String(value);
  }
}

/** Compact amount for a tight slot (the donut's 144px centre). */
function amountCompact(value: number, locale: string): string {
  if (!Number.isFinite(value)) return "—";
  try {
    return new Intl.NumberFormat(locale, {
      notation: "compact",
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return amountFull(value, locale);
  }
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

interface AmountItem {
  label: string;
  name?: string | null;
  amount: number;
  count: number;
  unconverted_count?: number;
}

interface AmountListProps {
  items: AmountItem[];
  currency: string;
  renderLabel?: (item: AmountItem) => React.ReactNode;
}

/** Bar list where the metric is money rather than a count (spec #28). */
function AmountList({ items, currency, renderLabel }: AmountListProps) {
  const { t, locale } = useI18n();
  const max = Math.max(1, ...items.map((item) => item.amount));
  const total = items.reduce((sum, item) => sum + item.amount, 0);

  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-sm font-medium">
                {renderLabel ? renderLabel(item) : (item.name || item.label)}
                {item.count > 0 ? (
                  <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                    {t("stats.expenseCountShort", { count: item.count })}
                  </span>
                ) : null}
              </span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                <span className="font-medium text-foreground">
                  {money(item.amount, currency, locale)}
                </span>
                <span className="ml-1.5 text-[10px]">{share(item.amount, total)}</span>
              </span>
            </div>
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary to-[#96670c] transition-all duration-500"
                style={{ width: `${(item.amount / max) * 100}%` }}
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
  const [spendYear, setSpendYear] = useState<string | null>(null);

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
    { label: t("dashboard.stats.hotels"), value: totals?.hotels ?? 0 },
    { label: t("dashboard.stats.trips"), value: totals?.trips ?? 0 },
  ];

  const mix: ChartDatum[] = [    { label: t("stats.group.flight"), value: totals?.flights ?? 0 },
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

  const expense = data?.expense_stats;
  const currency = expense?.report_currency ?? "CNY";
  const hasExpense = (expense?.count ?? 0) > 0;
  const showStats = Boolean(data && (journeys > 0 || hasExpense));

  const spendYears = useMemo(
    () =>
      Array.from(new Set((expense?.by_month ?? []).map((item) => item.label.slice(0, 4)))).sort(),
    [expense],
  );
  const spendMonthAmounts = useMemo(
    () => new Map((expense?.by_month ?? []).map((item) => [item.label, Number(item.amount)])),
    [expense],
  );
  const activeSpendYear =
    spendYear && spendYears.includes(spendYear) ? spendYear : spendYears.at(-1);
  const spendMonthData: ChartDatum[] = activeSpendYear
    ? Array.from({ length: 12 }, (_, index) => {
        const key = `${activeSpendYear}-${String(index + 1).padStart(2, "0")}`;
        return { label: key, value: spendMonthAmounts.get(key) ?? 0 };
      })
    : [];
  const categoryItems: AmountItem[] = (expense?.by_category ?? []).map((item) => ({
    ...item,
    amount: Number(item.amount),
  }));
  const sourceItems: AmountItem[] = (expense?.by_source_type ?? []).map((item) => ({
    ...item,
    amount: Number(item.amount),
  }));
  const tripItems: AmountItem[] = (expense?.by_trip ?? []).map((item) => ({
    ...item,
    amount: Number(item.amount),
  }));

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

      {data && !showStats ? (
        <EmptyState icon={BarChart3} title={t("stats.empty")} hint={t("stats.emptyHint")} />
      ) : null}

      {data && showStats ? (
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

          <section id="stats-expense" className="flex scroll-mt-24 flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {t("stats.expenseTitle")}
              </h2>
              <span className="text-xs text-muted-foreground">
                {t("stats.expenseReportCurrency", { currency })}
              </span>
            </div>

            {expense && hasExpense ? (
              <>
                <Card className="animate-fade-in-up">
                  <CardHeader className="flex-row items-center justify-between">
                    <CardTitle>{t("stats.expenseOverview")}</CardTitle>
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {t("stats.expenseCountShort", { count: expense.count })}
                    </span>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-4">
                    <div className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-4">
                      <Stat
                        label={t("stats.expenseTotal")}
                        value={money(expense.total, currency, locale)}
                      />
                      <Stat
                        label={t("stats.expenseAverage")}
                        value={money(expense.average, currency, locale)}
                      />
                      <Stat
                        label={t("stats.expenseLargest")}
                        value={money(expense.largest, currency, locale)}
                      />
                      <Stat label={t("stats.expenseUnconvertedCount")} value={expense.unconverted_count} />
                    </div>
                    {expense.unconverted.length > 0 ? (
                      <div className="flex flex-col gap-1.5">
                        <ul className="flex flex-wrap gap-2">
                          {expense.unconverted.map((item) => (
                            <li
                              key={item.currency}
                              className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground"
                            >
                              {item.currency} {item.amount}
                            </li>
                          ))}
                        </ul>
                        <p className="text-[11px] text-muted-foreground">
                          {t("stats.expenseUnconvertedHint")}
                        </p>
                      </div>
                    ) : null}
                    {expense.converted_count === 0 ? (
                      <p className="text-xs text-muted-foreground">
                        {t("stats.expenseAllUnconverted")}
                      </p>
                    ) : null}
                  </CardContent>
                </Card>

                <div className="grid gap-4 lg:grid-cols-3">
                  {categoryItems.length > 0 ? (
                    <Card className="animate-fade-in-up">
                      <CardHeader className="flex-row items-center justify-between">
                        <CardTitle>{t("stats.expenseByCategory")}</CardTitle>
                        <span className="text-xs tabular-nums text-muted-foreground">
                          {currency}
                        </span>
                      </CardHeader>
                      <CardContent>
                        <DonutChart
                          data={categoryItems.map((item) => ({
                            label: translate(EXPENSE_CATEGORY_KEYS)(item.label),
                            value: item.amount,
                          }))}
                          ariaLabel={t("stats.expenseByCategory")}
                          centerLabel={t("stats.expenseTotal")}
                          formatValue={(value) => amountFull(value, locale)}
                          formatCenter={(value) => amountCompact(value, locale)}
                        />
                      </CardContent>
                    </Card>
                  ) : null}

                  <Card className="animate-fade-in-up lg:col-span-2">
                    <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
                      <CardTitle>{t("stats.expenseMonthly")}</CardTitle>
                      {spendYears.length > 1 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {[...spendYears].reverse().map((year) => (
                            <button
                              key={year}
                              type="button"
                              onClick={() => setSpendYear(year)}
                              className={
                                year === activeSpendYear
                                  ? "rounded-full bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground"
                                  : "rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                              }
                            >
                              {year}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs tabular-nums text-muted-foreground">
                          {activeSpendYear}
                        </span>
                      )}
                    </CardHeader>
                    <CardContent>
                      <ColumnChart
                        data={spendMonthData}
                        ariaLabel={t("stats.expenseMonthly")}
                        formatLabel={monthLabel(locale)}
                        formatValue={(value) => money(value, currency, locale)}
                      />
                    </CardContent>
                  </Card>
                </div>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {sourceItems.length > 1 ? (
                    <Card className="animate-fade-in-up">
                      <CardHeader>
                        <CardTitle>{t("stats.expenseBySource")}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <AmountList
                          items={sourceItems}
                          currency={currency}
                          renderLabel={(item) => translate(EXPENSE_SOURCE_KEYS)(item.label)}
                        />
                      </CardContent>
                    </Card>
                  ) : null}

                  {(expense.by_currency?.length ?? 0) > 0 ? (
                    <Card className="animate-fade-in-up">
                      <CardHeader>
                        <CardTitle>{t("stats.expenseByCurrency")}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <AmountList
                          items={(expense.by_currency ?? []).map((item) => ({
                            label: item.currency,
                            amount: Number(item.amount),
                            count: item.count,
                          }))}
                          currency={currency}
                        />
                      </CardContent>
                    </Card>
                  ) : null}

                  {tripItems.length > 0 ? (
                    <Card className="animate-fade-in-up">
                      <CardHeader className="flex-row items-center justify-between">
                        <CardTitle>{t("stats.expenseByTrip")}</CardTitle>
                        <span className="text-xs text-muted-foreground">
                          {t("stats.expenseTopTrips")}
                        </span>
                      </CardHeader>
                      <CardContent>
                        <AmountList
                          items={tripItems}
                          currency={currency}
                          renderLabel={(item) => item.name || t("expenses.tripNone")}
                        />
                      </CardContent>
                    </Card>
                  ) : null}
                </div>
              </>
            ) : (
              <Card className="animate-fade-in-up">
                <CardContent>
                  <p className="text-sm text-muted-foreground">{t("stats.expenseEmpty")}</p>
                </CardContent>
              </Card>
            )}
          </section>

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
