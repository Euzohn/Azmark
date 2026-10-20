"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Backpack,
  BarChart3,
  Bus,
  Compass,
  Globe2,
  MapPin,
  Plane,
  TrainFront,
  type LucideIcon,
} from "lucide-react";

import { AirlineLogo } from "@/components/airline-logo";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { BreakdownItem } from "@/lib/types";

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

function BarList({
  items,
  renderLeading,
  formatLabel,
}: {
  items: BreakdownItem[];
  renderLeading?: (item: BreakdownItem) => React.ReactNode;
  formatLabel?: (label: string) => string;
}) {
  const max = Math.max(1, ...items.map((item) => item.count));
  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          {renderLeading ? renderLeading(item) : null}
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-sm font-medium">
                {formatLabel ? formatLabel(item.label) : item.label}
                {item.name ? (
                  <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                    {item.name}
                  </span>
                ) : null}
              </span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {item.count}
              </span>
            </div>
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary to-[#78816a] transition-all duration-500"
                style={{ width: `${(item.count / max) * 100}%` }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function monthLabel(label: string): string {
  return label.replace("-", "/");
}

function dayLabel(label: string): string {
  return label.replaceAll("-", "/");
}

function translateLabel(
  map: Record<string, TranslationKey>,
  label: string,
  t: (key: TranslationKey) => string,
): string {
  const key = map[label];
  return key ? t(key) : label;
}

function TotalTile({
  icon: Icon,
  label,
  value,
  delay = 0,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  delay?: number;
}) {
  return (
    <div
      className="flex animate-fade-in-up items-center gap-3"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <Icon className="h-5 w-5" strokeWidth={1.75} />
      </div>
      <div className="min-w-0">
        <div className="font-display text-2xl font-semibold leading-none tracking-tight">
          {value}
        </div>
        <div className="mt-1 truncate text-xs text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

interface StatsSection {
  key: string;
  title: string;
  items: BreakdownItem[];
  leading?: boolean;
  formatLabel?: (label: string) => string;
}

export default function StatisticsPage() {
  const { t } = useI18n();

  const { data, isLoading } = useQuery({
    queryKey: ["statistics"],
    queryFn: api.getStatistics,
  });

  const translate = (map: Record<string, TranslationKey>) => (label: string) =>
    translateLabel(map, label, t);

  const timeSections: StatsSection[] = data
    ? [
        { key: "year", title: t("stats.byYear"), items: data.by_year },
        {
          key: "month",
          title: t("stats.byMonth"),
          items: data.by_month,
          formatLabel: monthLabel,
        },
        {
          key: "day",
          title: t("stats.byDay"),
          items: data.by_day,
          formatLabel: dayLabel,
        },
      ]
    : [];

  const flightSections: StatsSection[] = data
    ? [
        { key: "airline", title: t("stats.byAirline"), items: data.by_airline, leading: true },
        { key: "aircraft", title: t("stats.byAircraft"), items: data.by_aircraft },
        { key: "airport", title: t("stats.byAirport"), items: data.by_airport },
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
      ]
    : [];

  const trainSections: StatsSection[] = data
    ? [
        {
          key: "operator",
          title: t("stats.byTrainOperator"),
          items: data.by_train_operator,
        },
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
      ]
    : [];

  const groups = [
    { key: "flight", title: t("stats.group.flight"), sections: flightSections },
    { key: "train", title: t("stats.group.train"), sections: trainSections },
    { key: "time", title: t("stats.group.time"), sections: timeSections },
  ]
    .map((group) => ({
      ...group,
      sections: group.sections.filter((section) => section.items.length > 0),
    }))
    .filter((group) => group.sections.length > 0);

  const hasRecords = Boolean(
    data &&
      (data.totals.flights > 0 ||
        data.totals.trains > 0 ||
        data.totals.transports > 0 ||
        data.totals.trips > 0),
  );

  const tiles = data
    ? [
        {
          icon: Globe2,
          label: t("dashboard.stats.countries"),
          value: data.totals.countries,
        },
        { icon: MapPin, label: t("dashboard.stats.cities"), value: data.totals.cities },
        {
          icon: Compass,
          label: t("dashboard.stats.distance"),
          value: `${Math.round(data.totals.distance_km).toLocaleString()} ${t("stats.km")}`,
        },
        { icon: Backpack, label: t("dashboard.stats.trips"), value: data.totals.trips },
        { icon: Plane, label: t("dashboard.stats.flights"), value: data.totals.flights },
        { icon: TrainFront, label: t("dashboard.stats.trains"), value: data.totals.trains },
        {
          icon: Bus,
          label: t("dashboard.stats.transports"),
          value: data.totals.transports,
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-6">
      <div className="animate-fade-in-up">
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          {t("stats.title")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("stats.subtitle")}</p>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-28 w-full" />
          <div className="grid gap-4 md:grid-cols-2">
            {Array.from({ length: 4 }, (_, index) => (
              <Skeleton key={index} className="h-48 w-full" />
            ))}
          </div>
        </div>
      ) : null}

      {data && !hasRecords ? (
        <EmptyState
          icon={BarChart3}
          title={t("stats.empty")}
          hint={t("stats.emptyHint")}
        />
      ) : null}

      {data && hasRecords ? (
        <>
          <Card className="animate-fade-in-up">
            <CardContent className="grid grid-cols-2 gap-x-4 gap-y-5 p-5 sm:grid-cols-3 lg:grid-cols-4">
              {tiles.map((tile, index) => (
                <TotalTile
                  key={tile.label}
                  icon={tile.icon}
                  label={tile.label}
                  value={tile.value}
                  delay={index * 35}
                />
              ))}
            </CardContent>
          </Card>

          {groups.map((group, groupIndex) => (
            <section key={group.key} className="flex flex-col gap-3">
              <h2
                className="animate-fade-in-up text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground"
                style={{ animationDelay: `${groupIndex * 60}ms` }}
              >
                {group.title}
              </h2>
              <div className="grid gap-4 md:grid-cols-2">
                {group.sections.map((section, sectionIndex) => (
                  <Card
                    key={section.key}
                    className="animate-fade-in-up"
                    style={{ animationDelay: `${groupIndex * 60 + sectionIndex * 40}ms` }}
                  >
                    <CardHeader>
                      <CardTitle>{section.title}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <BarList
                        items={section.items}
                        formatLabel={section.formatLabel}
                        renderLeading={
                          section.leading
                            ? (item) => <AirlineLogo code={item.label} className="h-8 w-8" />
                            : undefined
                        }
                      />
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          ))}
        </>
      ) : null}
    </div>
  );
}
