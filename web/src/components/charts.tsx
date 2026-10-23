"use client";

import { cn } from "@/lib/utils";

/**
 * Dependency-free charts for the dashboard and statistics pages.
 *
 * They deliberately stay inside the "Ink & Saffron" system: one accent hue,
 * warm neutrals, no extra chart palette. Bars are plain DOM (crisp at any
 * width, trivially responsive), the donut is SVG so the arcs stay exact.
 * Every chart carries an accessible summary and per-item labels.
 */

export interface ChartDatum {
  label: string;
  value: number;
}

/** Primary-hue shades, darkest first. Keeps multi-series charts on-brand. */
const SHADES = [100, 78, 58, 42, 30, 21, 14];

function shade(index: number): string {
  const lightness = SHADES[index % SHADES.length];
  return `color-mix(in srgb, var(--primary) ${lightness}%, var(--card))`;
}

interface ColumnChartProps {
  data: ChartDatum[];
  /** Accessible summary, e.g. "Monthly departures, 12 months". */
  ariaLabel: string;
  /** Height of the plot area in pixels. */
  height?: number;
  formatValue?: (value: number) => string;
  formatLabel?: (label: string) => string;
  className?: string;
}

export function ColumnChart({
  data,
  ariaLabel,
  height = 168,
  formatValue = (value) => String(value),
  formatLabel = (label) => label,
  className,
}: ColumnChartProps) {
  const max = Math.max(1, ...data.map((item) => item.value));
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <figure className={cn("flex flex-col gap-2.5", className)} aria-label={ariaLabel}>
      <div className="relative flex items-end gap-1.5" style={{ height }}>
        <div aria-hidden className="pointer-events-none absolute inset-0 flex flex-col justify-between">
          {[0, 1, 2, 3].map((line) => (
            <div key={line} className="border-t border-border/70" />
          ))}
        </div>
        {data.map((item, index) => {
          const ratio = item.value / max;
          return (
            <div
              key={`${item.label}-${index}`}
              className="group relative flex h-full min-w-0 flex-1 items-end justify-center"
              title={`${formatLabel(item.label)} · ${formatValue(item.value)}`}
              aria-label={`${formatLabel(item.label)}: ${formatValue(item.value)}`}
            >
              <span className="pointer-events-none absolute -top-1 left-1/2 z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md border border-border bg-card px-2 py-1 text-[11px] font-medium tabular-nums text-foreground opacity-0 shadow-sm transition-opacity duration-150 group-hover:opacity-100">
                {formatValue(item.value)}
              </span>
              <div
                className={cn(
                  "w-full max-w-9 rounded-t-[5px] transition-[height,background-color] duration-500 ease-out",
                  item.value === 0
                    ? "bg-border"
                    : "bg-primary/75 group-hover:bg-primary",
                )}
                style={{ height: item.value === 0 ? 2 : `${Math.max(ratio * 100, 3)}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex gap-1.5" aria-hidden>
        {data.map((item, index) => (
          <div
            key={`${item.label}-label-${index}`}
            className="min-w-0 flex-1 truncate text-center text-[10px] leading-4 text-muted-foreground"
          >
            {formatLabel(item.label)}
          </div>
        ))}
      </div>
      <figcaption className="sr-only">
        {ariaLabel}: {total}
      </figcaption>
    </figure>
  );
}

interface DonutChartProps {
  data: ChartDatum[];
  ariaLabel: string;
  /** Text shown under the number in the middle of the ring. */
  centerLabel: string;
  formatValue?: (value: number) => string;
  formatLabel?: (label: string) => string;
  className?: string;
}

export function DonutChart({
  data,
  ariaLabel,
  centerLabel,
  formatValue = (value) => String(value),
  formatLabel = (label) => label,
  className,
}: DonutChartProps) {
  const items = data.filter((item) => item.value > 0);
  const total = items.reduce((sum, item) => sum + item.value, 0);
  const segments = items.map((item, index) => {
    const portion = (item.value / Math.max(total, 1)) * 100;
    const gap = portion > 3 ? 1.4 : 0;
    const offset = items
      .slice(0, index)
      .reduce((sum, previous) => sum + (previous.value / Math.max(total, 1)) * 100, 0);
    return {
      item,
      dash: Math.max(portion - gap, 0.6),
      offset,
    };
  });

  return (
    <div className={cn("flex flex-col gap-5 sm:flex-row sm:items-center", className)}>
      <div
        className="relative mx-auto h-36 w-36 shrink-0"
        role="img"
        aria-label={`${ariaLabel}: ${formatValue(total)}`}
      >
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke="var(--muted)"
            strokeWidth="11"
          />
          {segments.map(({ item, dash, offset }, index) => {
            return (
              <circle
                key={`${item.label}-${index}`}
                cx="50"
                cy="50"
                r="40"
                pathLength={100}
                fill="none"
                stroke={shade(index)}
                strokeWidth="11"
                strokeLinecap="butt"
                strokeDasharray={`${dash} ${100 - dash}`}
                strokeDashoffset={-offset}
                className="transition-all duration-500"
              >
                <title>{`${formatLabel(item.label)}: ${formatValue(item.value)}`}</title>
              </circle>
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <span className="font-display text-2xl font-semibold tabular-nums text-foreground">
            {formatValue(total)}
          </span>
          <span className="max-w-[5.5rem] text-center text-[10px] leading-3 text-muted-foreground">
            {centerLabel}
          </span>
        </div>
      </div>

      <ul className="flex min-w-0 flex-1 flex-col gap-2">
        {items.map((item, index) => (
          <li key={`${item.label}-legend-${index}`} className="flex items-center gap-2 text-sm">
            <span
              aria-hidden
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: shade(index) }}
            />
            <span className="min-w-0 flex-1 truncate text-muted-foreground">
              {formatLabel(item.label)}
            </span>
            <span className="shrink-0 tabular-nums font-medium text-foreground">
              {formatValue(item.value)}
            </span>
            <span className="w-9 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
              {Math.round((item.value / Math.max(total, 1)) * 100)}%
            </span>
          </li>
        ))}
        {items.length === 0 ? (
          <li className="text-sm text-muted-foreground">—</li>
        ) : null}
      </ul>
    </div>
  );
}

interface ShareBarProps {
  data: ChartDatum[];
  ariaLabel: string;
  formatLabel?: (label: string) => string;
  className?: string;
}

export function ShareBar({
  data,
  ariaLabel,
  formatLabel = (label) => label,
  className,
}: ShareBarProps) {
  const items = data.filter((item) => item.value > 0);
  const total = items.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div
        className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={ariaLabel}
      >
        {items.map((item, index) => (
          <div
            key={`${item.label}-${index}`}
            title={`${formatLabel(item.label)}: ${item.value}`}
            className="h-full transition-all duration-500 first:rounded-l-full last:rounded-r-full"
            style={{
              width: `${(item.value / Math.max(total, 1)) * 100}%`,
              backgroundColor: shade(index),
            }}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
        {items.map((item, index) => (
          <li key={`${item.label}-legend-${index}`} className="flex items-center gap-1.5 text-xs">
            <span
              aria-hidden
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: shade(index) }}
            />
            <span className="text-muted-foreground">{formatLabel(item.label)}</span>
            <span className="tabular-nums font-medium text-foreground">{item.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
