"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Bus,
  ChevronLeft,
  ChevronRight,
  Gift,
  MapPin,
  Plane,
  Star,
  TrainFront,
} from "lucide-react";
import Link from "next/link";
import {
  createContext,
  Suspense,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

import { ColumnChart, type ChartDatum } from "@/components/charts";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type {
  BreakdownItem,
  MapPoint,
  WrappedRead,
  WrappedRoute,
  WrappedTotals,
} from "@/lib/types";
import { cn } from "@/lib/utils";

/** Chapter visibility, shared down the tree so CountUp and bars key off the
 *  same reveal beat as the staggered opacity animation. */
const ChapterVisibleContext = createContext(false);

/** One-shot visibility flag: a chapter reveals once and stays revealed. */
function useInView<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      const frame = requestAnimationFrame(() => setInView(true));
      return () => cancelAnimationFrame(frame);
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.18, rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return { ref, inView };
}

/** Animated counter that eases to `value` once its chapter is visible. */
function CountUp({ value, className }: { value: number; className?: string }) {
  const active = useContext(ChapterVisibleContext);
  const { locale } = useI18n();
  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    if (!active) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const frame = requestAnimationFrame(() => setDisplay(value));
      return () => cancelAnimationFrame(frame);
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / 900, 1);
      setDisplay(Math.round(value * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [active, value]);
  return <span className={className}>{numbers.format(display)}</span>;
}

function staggerStyle(index: number, step = 80): CSSProperties {
  return { "--stagger-delay": `${index * step}ms` } as CSSProperties;
}

function fmtDate(iso: string, locale: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, (month ?? 1) - 1, day ?? 1).toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function pointLabel(point: MapPoint, locale: string): string {
  if (locale === "zh-CN") return point.name_zh ?? point.name ?? point.code ?? "";
  return point.name ?? point.code ?? "";
}

/** Editorially-styled numbered chapter: hairline kicker, generous spacing,
 *  scroll reveal with staggered children. */
function Chapter({
  index,
  id,
  label,
  children,
}: {
  index: number;
  id: string;
  label: string;
  children: ReactNode;
}) {
  const { ref, inView } = useInView<HTMLElement>();
  return (
    <section
      id={id}
      data-chapter={id}
      ref={ref}
      className={cn(
        "reveal scroll-mt-28 border-t border-border/50 py-14 sm:py-20",
        inView && "is-visible",
      )}
    >
      <ChapterVisibleContext.Provider value={inView}>
        <header className="flex items-center gap-3">
          <span className="font-display text-xs font-semibold tabular-nums tracking-[0.18em] text-primary/80">
            {String(index).padStart(2, "0")}
          </span>
          <span aria-hidden className="h-px w-8 bg-border" />
          <h2 className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
            {label}
          </h2>
        </header>
        <div className="mt-8 sm:mt-10">{children}</div>
      </ChapterVisibleContext.Provider>
    </section>
  );
}

function Stat({
  value,
  label,
  detail,
  index,
}: {
  value: number;
  label: string;
  detail?: string;
  index: number;
}) {
  return (
    <div className="stagger flex flex-col gap-1" style={staggerStyle(index)}>
      <CountUp
        value={value}
        className="font-display text-4xl font-semibold tabular-nums tracking-tight sm:text-5xl"
      />
      <span className="text-sm text-muted-foreground">{label}</span>
      {detail ? <span className="text-xs text-muted-foreground/70">{detail}</span> : null}
    </div>
  );
}

function ModeStat({
  value,
  label,
  color,
  index,
}: {
  value: number;
  label: string;
  color: string;
  index: number;
}) {
  return (
    <div className="stagger flex flex-col gap-1.5" style={staggerStyle(index)}>
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
        {label}
      </span>
      <CountUp
        value={value}
        className="font-display text-4xl font-semibold tabular-nums tracking-tight sm:text-5xl"
      />
    </div>
  );
}

/** Ranked bar list; the name follows the locale convention (zh: name ?? label). */
function TopList({
  title,
  items,
  index,
}: {
  title: string;
  items: BreakdownItem[];
  index: number;
}) {
  const { locale } = useI18n();
  const active = useContext(ChapterVisibleContext);
  if (items.length === 0) return null;
  const max = items[0]?.count ?? 1;
  return (
    <div className="stagger flex flex-col gap-2.5" style={staggerStyle(index)}>
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <ol className="flex flex-col gap-2">
        {items.map((item, rank) => {
          const name = locale === "zh-CN" ? (item.name ?? item.label) : item.label;
          return (
            <li key={item.label} className="flex items-center gap-3">
              <span className="w-4 shrink-0 text-right font-display text-xs tabular-nums text-muted-foreground/70">
                {rank + 1}
              </span>
              <span className="w-28 shrink-0 truncate text-sm sm:w-36">{name}</span>
              <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
                <span
                  className="block h-full rounded-full bg-primary/70 transition-[width] duration-700 ease-out"
                  style={{ width: active ? `${(item.count / max) * 100}%` : "0%" }}
                />
              </span>
              <span className="w-8 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                {item.count}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function ModeShare({ totals }: { totals: WrappedTotals }) {
  const { t } = useI18n();
  const active = useContext(ChapterVisibleContext);
  const modes = [
    { key: "flight", label: t("wrapped.flights"), count: totals.flights, color: "var(--mode-flight)" },
    { key: "train", label: t("wrapped.trains"), count: totals.trains, color: "var(--mode-train)" },
    { key: "other", label: t("wrapped.transports"), count: totals.transports, color: "var(--mode-other)" },
  ];
  const total = modes.reduce((sum, mode) => sum + mode.count, 0);
  if (total === 0) return null;
  const visible = modes.filter((mode) => mode.count > 0);
  return (
    <div className="stagger flex flex-col gap-3" style={staggerStyle(3, 60)}>
      <div
        className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={t("wrapped.moves")}
      >
        {visible.map((mode) => (
          <div
            key={mode.key}
            title={`${mode.label}: ${mode.count}`}
            className="h-full transition-[width] duration-700 ease-out first:rounded-l-full last:rounded-r-full"
            style={{
              width: active ? `${(mode.count / total) * 100}%` : "0%",
              backgroundColor: mode.color,
            }}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-5 gap-y-1.5">
        {visible.map((mode) => (
          <li key={mode.key} className="flex items-center gap-1.5 text-xs">
            <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: mode.color }} />
            <span className="text-muted-foreground">{mode.label}</span>
            <span className="font-medium tabular-nums">{mode.count}</span>
            <span className="tabular-nums text-muted-foreground/70">
              {Math.round((mode.count / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RouteArc({ route }: { route: WrappedRoute }) {
  const { t, locale } = useI18n();
  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const active = useContext(ChapterVisibleContext);
  const href =
    route.type === "train" ? `/trains/${route.id}` : route.type === "other" ? `/transports/${route.id}` : `/flights/${route.id}`;
  const ModeIcon = route.type === "train" ? TrainFront : route.type === "other" ? Bus : Plane;
  const originTitle = route.origin.code ?? pointLabel(route.origin, locale);
  const destinationTitle = route.destination.code ?? pointLabel(route.destination, locale);
  const originSub =
    locale === "zh-CN" ? (route.origin.city_zh ?? route.origin.city) : route.origin.city;
  const destinationSub =
    locale === "zh-CN" ? (route.destination.city_zh ?? route.destination.city) : route.destination.city;
  return (
    <div className="flex flex-col gap-6">
      <div className="stagger relative" style={staggerStyle(0)}>
        <svg
          viewBox="0 0 480 150"
          aria-hidden
          className="h-36 w-full text-primary/60 sm:h-44"
        >
          <path
            d="M24 132 C 140 16, 340 16, 456 132"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="5 7"
            strokeLinecap="round"
            className={active ? "animate-dash-flow" : undefined}
          />
          <circle cx="24" cy="132" r="4" fill="var(--primary)" />
          <circle cx="456" cy="132" r="4" fill="var(--primary)" />
        </svg>
        <span className="absolute inset-x-0 top-0 flex justify-center">
          <span className="flex items-center gap-1.5 rounded-full border border-border/60 bg-card/80 px-3 py-1 text-xs tabular-nums text-muted-foreground">
            <ModeIcon className="h-3.5 w-3.5" />
            {numbers.format(Math.round(route.distance_km))} {t("stats.km")}
          </span>
        </span>
      </div>
      <div className="flex items-end justify-between gap-4">
        <div className="stagger min-w-0" style={staggerStyle(1)}>
          <p className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            {originTitle}
          </p>
          {originSub && originSub !== originTitle ? (
            <p className="mt-1 truncate text-sm text-muted-foreground">{originSub}</p>
          ) : null}
        </div>
        <div className="stagger min-w-0 text-right" style={staggerStyle(2)}>
          <p className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            {destinationTitle}
          </p>
          {destinationSub && destinationSub !== destinationTitle ? (
            <p className="mt-1 truncate text-sm text-muted-foreground">{destinationSub}</p>
          ) : null}
        </div>
      </div>
      <div
        className="stagger flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground"
        style={staggerStyle(3)}
      >
        {route.carrier ? <span>{route.carrier}</span> : null}
        {route.service_number ? <span className="tabular-nums">{route.service_number}</span> : null}
        {route.departure_date ? <span>{fmtDate(route.departure_date, locale)}</span> : null}
        <Link
          href={href}
          className="inline-flex items-center gap-1 font-medium text-primary transition-opacity hover:opacity-80"
        >
          {t("wrapped.viewJourney")}
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}

function Cover({ wrapped, journeys }: { wrapped: WrappedRead; journeys: number }) {
  const { t, locale } = useI18n();
  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const { ref, inView } = useInView<HTMLElement>();
  return (
    <section
      id="cover"
      data-chapter="cover"
      ref={ref}
      className={cn(
        "reveal relative flex flex-col items-center gap-5 overflow-hidden pb-14 pt-12 text-center sm:pb-20 sm:pt-16",
        inView && "is-visible",
      )}
    >
      <ChapterVisibleContext.Provider value={inView}>
        <svg
          viewBox="0 0 560 200"
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 mx-auto h-44 w-full max-w-xl text-border/80"
        >
          <path
            d="M12 188 C 152 16, 408 16, 548 188"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="4 9"
            strokeLinecap="round"
            className="animate-dash-flow"
          />
        </svg>
        <p
          className="stagger relative text-[11px] font-medium uppercase tracking-[0.32em] text-muted-foreground"
          style={staggerStyle(0)}
        >
          {t("wrapped.subtitle", { year: wrapped.year })}
        </p>
        <h2
          className="stagger relative font-display text-[clamp(4.5rem,17vw,9.5rem)] font-semibold leading-none tracking-[-0.04em] tabular-nums"
          style={staggerStyle(1)}
        >
          {wrapped.year}
        </h2>
        <div className="stagger relative flex flex-col items-center gap-1.5" style={staggerStyle(2)}>
          <p className="flex items-baseline gap-2">
            <CountUp
              value={journeys}
              className="font-display text-3xl font-semibold tabular-nums sm:text-4xl"
            />
            <span className="text-sm text-muted-foreground">{t("wrapped.journeysLabel")}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            {t("wrapped.distance", { value: numbers.format(Math.round(wrapped.totals.distance_km)) })}
          </p>
        </div>
        {wrapped.first_journey && wrapped.last_journey ? (
          <p className="stagger relative text-xs text-muted-foreground/80" style={staggerStyle(3)}>
            {t("wrapped.firstJourney", { date: fmtDate(wrapped.first_journey, locale) })} ·{" "}
            {t("wrapped.lastJourney", { date: fmtDate(wrapped.last_journey, locale) })}
          </p>
        ) : null}
      </ChapterVisibleContext.Provider>
    </section>
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
  const [activeChapter, setActiveChapter] = useState("cover");

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

  // Track which chapter crosses the middle of the viewport, for the rail.
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    const sections = Array.from(container.querySelectorAll<HTMLElement>("[data-chapter]"));
    if (sections.length === 0 || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting);
        if (visible.length === 0) return;
        const topmost = visible.reduce((a, b) =>
          a.boundingClientRect.top < b.boundingClientRect.top ? a : b,
        );
        setActiveChapter(topmost.target.getAttribute("data-chapter") ?? "cover");
      },
      { rootMargin: "-40% 0px -50% 0px" },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [data?.year]);

  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const monthsShort = useMemo(
    () => new Intl.DateTimeFormat(locale, { month: "short" }),
    [locale],
  );
  const monthsLong = useMemo(
    () => new Intl.DateTimeFormat(locale, { month: "long" }),
    [locale],
  );

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

  const monthOf = (label: string) => {
    const [yearPart, monthPart] = label.split("-");
    return new Date(Number(yearPart), Number(monthPart) - 1, 1);
  };
  const monthData: ChartDatum[] = wrapped.by_month.map((item) => ({
    label: item.label,
    value: item.count,
  }));
  const peak = wrapped.by_month.reduce<BreakdownItem | null>(
    (best, item) => (best === null || item.count > best.count ? item : best),
    null,
  );

  const scrollChapter = (direction: 1 | -1) => {
    const container = scrollRef.current;
    if (!container) return;
    const sections = Array.from(container.querySelectorAll<HTMLElement>("[data-chapter]"));
    if (sections.length === 0) return;
    // The chapter occupying the viewport centre is the one the reader is on.
    const mid = window.innerHeight / 2;
    let current = 0;
    sections.forEach((section, index) => {
      if (section.getBoundingClientRect().top <= mid) current = index;
    });
    const target = Math.max(0, Math.min(sections.length - 1, current + direction));
    sections[target]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const chapters: { id: string; label: string; content: ReactNode }[] = [
    {
      id: "footprint",
      label: t("wrapped.footprint"),
      content: (
        <div className="flex flex-col gap-8">
          <div className="grid grid-cols-3 gap-6">
            <Stat value={totals.countries} label={t("wrapped.countries")} index={0} />
            <Stat value={totals.cities} label={t("wrapped.cities")} index={1} />
            <Stat value={totals.travel_days} label={t("wrapped.travelDays")} index={2} />
          </div>
          <p className="stagger text-sm text-muted-foreground" style={staggerStyle(3)}>
            {t("wrapped.journeySpan", { year: wrapped.year, days: totals.travel_days })}
          </p>
        </div>
      ),
    },
    {
      id: "moves",
      label: t("wrapped.moves"),
      content: (
        <div className="flex flex-col gap-10">
          <div className="grid grid-cols-3 gap-6">
            <ModeStat
              value={totals.flights}
              label={t("wrapped.flights")}
              color="var(--mode-flight)"
              index={0}
            />
            <ModeStat
              value={totals.trains}
              label={t("wrapped.trains")}
              color="var(--mode-train)"
              index={1}
            />
            <ModeStat
              value={totals.transports}
              label={t("wrapped.transports")}
              color="var(--mode-other)"
              index={2}
            />
          </div>
          <ModeShare totals={totals} />
          <div className="grid gap-8 sm:grid-cols-2">
            <TopList title={t("wrapped.topAirlines")} items={wrapped.top_airlines} index={4} />
            <TopList title={t("wrapped.topAirports")} items={wrapped.top_airports} index={5} />
            <TopList title={t("wrapped.topStations")} items={wrapped.top_stations} index={6} />
            <TopList title={t("wrapped.topAircraft")} items={wrapped.top_aircraft} index={7} />
          </div>
        </div>
      ),
    },
  ];

  if (wrapped.most_visited_city || wrapped.favorite_trip) {
    chapters.push({
      id: "favorites",
      label: t("wrapped.favorites"),
      content: (
        <div className="grid gap-6 sm:grid-cols-2">
          {wrapped.most_visited_city ? (
            <div
              className="stagger flex flex-col gap-3 rounded-2xl border border-border/60 bg-card/50 p-6 sm:p-7"
              style={staggerStyle(0)}
            >
              <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                <MapPin className="h-3.5 w-3.5" />
                {t("wrapped.mostVisitedCity")}
              </p>
              <p className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">
                {locale === "zh-CN"
                  ? (wrapped.most_visited_city.name ?? wrapped.most_visited_city.label)
                  : wrapped.most_visited_city.label}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("wrapped.visits", { count: wrapped.most_visited_city.count })}
              </p>
            </div>
          ) : null}
          {wrapped.favorite_trip ? (
            <div
              className="stagger flex flex-col gap-3 rounded-2xl border border-border/60 bg-card/50 p-6 sm:p-7"
              style={staggerStyle(1)}
            >
              <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                <Star className="h-3.5 w-3.5" />
                {t("wrapped.favoriteTrip")}
              </p>
              <p className="truncate font-display text-2xl font-semibold tracking-tight sm:text-3xl">
                {wrapped.favorite_trip.name ?? wrapped.favorite_trip.label}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("wrapped.journeysCount", { count: wrapped.favorite_trip.count })}
              </p>
            </div>
          ) : null}
        </div>
      ),
    });
  }

  if (wrapped.longest_route) {
    chapters.push({
      id: "longest",
      label: t("wrapped.longest"),
      content: <RouteArc route={wrapped.longest_route} />,
    });
  }

  if (totals.trips + totals.hotels + totals.activities > 0) {
    chapters.push({
      id: "stays",
      label: t("wrapped.trips"),
      content: (
        <div className="grid grid-cols-3 gap-6">
          <Stat value={totals.trips} label={t("wrapped.trips")} index={0} />
          <Stat
            value={totals.hotels}
            label={t("wrapped.hotels")}
            detail={totals.hotel_nights > 0 ? t("wrapped.nights", { count: totals.hotel_nights }) : undefined}
            index={1}
          />
          <Stat value={totals.activities} label={t("wrapped.activities")} index={2} />
        </div>
      ),
    });
  }

  if (spend.converted_count > 0 || spend.unconverted_count > 0) {
    chapters.push({
      id: "spend",
      label: t("wrapped.spend"),
      content: (
        <div className="flex flex-col gap-5">
          {spend.converted_count > 0 ? (
            <>
              <div className="stagger flex items-baseline gap-2.5" style={staggerStyle(0)}>
                <span className="font-display text-4xl font-semibold tabular-nums tracking-tight sm:text-5xl">
                  {numbers.format(Number(spend.converted_total))}
                </span>
                <span className="text-lg text-muted-foreground">{spend.report_currency}</span>
              </div>
              <p className="stagger text-sm text-muted-foreground" style={staggerStyle(1)}>
                {t("wrapped.spendConverted", {
                  count: spend.converted_count,
                  currency: spend.report_currency,
                })}
              </p>
            </>
          ) : null}
          {spend.unconverted.length > 0 ? (
            <p className="stagger text-xs text-muted-foreground/80" style={staggerStyle(2)}>
              {t("wrapped.spendUnconverted", {
                count: spend.unconverted_count,
                items: spend.unconverted
                  .map((bucket) => `${numbers.format(Number(bucket.amount))} ${bucket.currency}`)
                  .join(" · "),
              })}
            </p>
          ) : null}
        </div>
      ),
    });
  }

  if (wrapped.by_month.length > 0) {
    chapters.push({
      id: "rhythm",
      label: t("wrapped.rhythm"),
      content: (
        <div className="flex flex-col gap-8">
          <div className="stagger" style={staggerStyle(0)}>
            <ColumnChart
              data={monthData}
              ariaLabel={t("wrapped.rhythm")}
              height={208}
              formatLabel={(label) => monthsShort.format(monthOf(label))}
            />
          </div>
          {peak && peak.count > 0 ? (
            <div
              className="stagger flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/60 bg-card/50 px-5 py-4"
              style={staggerStyle(3)}
            >
              <p className="text-sm font-medium text-foreground">
                {t("wrapped.peakMonth", { month: monthsLong.format(monthOf(peak.label)) })}
              </p>
              <p className="text-sm tabular-nums text-muted-foreground">
                {t("wrapped.peakMonthValue", { count: peak.count })}
              </p>
            </div>
          ) : null}
        </div>
      ),
    });
  }

  const rail = [
    { id: "cover", label: String(wrapped.year) },
    ...chapters.map((chapter) => ({ id: chapter.id, label: chapter.label })),
  ];

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

      {/* key remounts the whole report on year switch, resetting reveals. */}
      <div key={wrapped.year} className="flex items-start gap-12">
        <div ref={scrollRef} className="min-w-0 flex-1">
          <Cover wrapped={wrapped} journeys={journeys} />
          {chapters.map((chapter, index) => (
            <Chapter
              key={chapter.id}
              index={index + 1}
              id={chapter.id}
              label={chapter.label}
            >
              {chapter.content}
            </Chapter>
          ))}

          <div className="flex flex-col items-center gap-6 py-16 text-center sm:py-24">
            <span aria-hidden className="h-px w-16 bg-border" />
            <p className="max-w-md font-display text-xl leading-relaxed text-foreground/90 sm:text-2xl">
              {t("wrapped.closing")}
            </p>
            <Link
              href="/statistics"
              className="inline-flex h-9 items-center justify-center rounded-md border border-border px-4 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              {t("wrapped.back")}
            </Link>
          </div>
        </div>

        <nav
          aria-label={t("wrapped.chapters")}
          className="sticky top-28 hidden h-fit w-44 shrink-0 flex-col gap-0.5 xl:flex"
        >
          {rail.map(({ id, label }) => (
            <a
              key={id}
              href={`#${id}`}
              className={cn(
                "group flex items-center gap-2.5 rounded-lg px-2 py-2 text-xs transition-colors",
                activeChapter === id
                  ? "text-foreground"
                  : "text-muted-foreground/70 hover:text-foreground",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "h-1.5 w-1.5 shrink-0 rounded-full transition-all duration-300",
                  activeChapter === id
                    ? "scale-125 bg-primary"
                    : "bg-border group-hover:bg-muted-foreground/60",
                )}
              />
              <span className="truncate">{label}</span>
            </a>
          ))}
        </nav>
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