"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";

import { AirlineLogo } from "@/components/airline-logo";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { BreakdownItem } from "@/lib/types";

function BarList({
  items,
  renderLeading,
}: {
  items: BreakdownItem[];
  renderLeading?: (item: BreakdownItem) => React.ReactNode;
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
                {item.label}
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
                className="h-full rounded-full bg-primary/80"
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
  const [year, month] = label.split("-");
  if (!year || !month) return label;
  return `${year}/${month}`;
}

function allianceLabel(label: string): TranslationKey | null {
  switch (label) {
    case "star_alliance":
      return "alliance.star_alliance";
    case "skyteam":
      return "alliance.skyteam";
    case "oneworld":
      return "alliance.oneworld";
    default:
      return null;
  }
}

export default function StatisticsPage() {
  const { t } = useI18n();

  const { data, isLoading } = useQuery({
    queryKey: ["statistics"],
    queryFn: api.getStatistics,
  });

  const isEmpty =
    data &&
    data.by_month.length === 0 &&
    data.by_airline.length === 0 &&
    data.by_alliance.length === 0 &&
    data.by_airport.length === 0 &&
    data.by_aircraft.length === 0;

  const sections: { title: string; items: BreakdownItem[]; leading?: boolean }[] = data
    ? [
        { title: t("stats.byMonth"), items: data.by_month },
        { title: t("stats.byAirline"), items: data.by_airline, leading: true },
        { title: t("stats.byAlliance"), items: data.by_alliance },
        { title: t("stats.byAirport"), items: data.by_airport },
        { title: t("stats.byAircraft"), items: data.by_aircraft },
      ]
    : [];

  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-display text-3xl font-semibold tracking-tight">
        {t("stats.title")}
      </h1>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-48 w-full" />
          ))}
        </div>
      ) : null}

      {isEmpty ? (
        <EmptyState
          icon={BarChart3}
          title={t("stats.empty")}
          hint={t("stats.emptyHint")}
        />
      ) : null}

      {data && !isEmpty ? (
        <div className="grid gap-4 md:grid-cols-2">
          {sections
            .filter((section) => section.items.length > 0)
            .map((section) => (
              <Card key={section.title}>
                <CardHeader>
                  <CardTitle>{section.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <BarList
                    items={section.items.map((item) => {
                      if (section.title === t("stats.byMonth")) {
                        return { ...item, label: monthLabel(item.label) };
                      }
                      const allianceKey = allianceLabel(item.label);
                      if (allianceKey) {
                        return { ...item, label: t(allianceKey) };
                      }
                      return item;
                    })}
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
      ) : null}
    </div>
  );
}
