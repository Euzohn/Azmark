"use client";

import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: LucideIcon;
}

interface SegmentedProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: SegmentedOption<T>[];
  className?: string;
  size?: "sm" | "md";
}

/**
 * Pill segmented control — used for list/timeline view switches and tab-like
 * toggles inside a page (not primary navigation).
 */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
  size = "sm",
}: SegmentedProps<T>) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border bg-muted/60 p-1",
        className,
      )}
      role="tablist"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        const Icon = opt.icon;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-medium transition-all duration-200",
              size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm",
              active
                ? "bg-card text-foreground shadow-sm shadow-black/5"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {Icon ? <Icon className="h-3.5 w-3.5" strokeWidth={active ? 2.25 : 1.75} /> : null}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
