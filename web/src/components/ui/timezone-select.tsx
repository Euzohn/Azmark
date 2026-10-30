"use client";

import { Check, ChevronDown } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { useI18n } from "@/lib/i18n";
import {
  COMMON_TIMEZONES,
  filterTimezones,
  timezoneOffsetLabel,
} from "@/lib/timezones";
import { cn } from "@/lib/utils";

interface TimezoneSelectProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  /** Allow clearing the value (record forms do; the profile setting does not). */
  allowEmpty?: boolean;
}

/**
 * Options shown for a given search text. Empty query → the common zones plus
 * the current value; non-empty → name/offset search results.
 */
function buildOptions(query: string, value: string, allowEmpty: boolean): string[] {
  if (query.trim()) return filterTimezones(query);
  const result: string[] = [];
  if (allowEmpty) result.push("");
  if (value && !result.includes(value)) result.push(value);
  for (const zone of COMMON_TIMEZONES) {
    if (!result.includes(zone)) result.push(zone);
  }
  return result;
}

/**
 * Searchable IANA timezone picker (flight / train / transport forms, profile).
 *
 * `Intl.supportedValuesOf("timeZone")` yields 400+ zones, which is unusable as
 * a plain <select>. Opening the picker shows the common zones; typing filters
 * by name ("new york") or UTC offset ("+8", "utc+5:30"). Arrow keys move,
 * Enter commits, Escape closes.
 */
export function TimezoneSelect({
  value,
  onChange,
  className,
  allowEmpty = true,
}: TimezoneSelectProps) {
  const { t } = useI18n();
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  /** Empty query → common zones (plus the current one); otherwise search. */
  const options = useMemo(
    () => buildOptions(query, value, allowEmpty),
    [query, value, allowEmpty],
  );

  const openPicker = () => {
    const initial = buildOptions("", value, allowEmpty);
    const index = initial.indexOf(value);
    setQuery("");
    setActive(index < 0 ? 0 : index);
    setOpen(true);
  };

  const closePicker = () => {
    setOpen(false);
    setQuery("");
  };

  const commit = (next: string) => {
    onChange(next);
    // Do not refocus: a focus handler would immediately reopen the picker
    // (and on touch the tap has already blurred the field).
    closePicker();
  };

  // Click outside closes without committing the typed text.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) closePicker();
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Keep the highlighted row visible while arrowing through the list.
  useEffect(() => {
    if (!open) return;
    const node = listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`);
    node?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        openPicker();
        return;
      }
      if (options.length === 0) return;
      setActive((index) => Math.min(index + 1, options.length - 1));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        openPicker();
        return;
      }
      if (options.length === 0) return;
      setActive((index) => Math.max(index - 1, 0));
      return;
    }
    if (event.key === "Enter") {
      if (!open) return; // closed: let the form submit
      event.preventDefault();
      const next = options[active];
      if (next !== undefined) commit(next);
      return;
    }
    if (event.key === "Escape") {
      if (!open) return;
      event.preventDefault();
      closePicker();
      return;
    }
    if (event.key === "Tab") closePicker();
  };

  const inputValue = open ? query : value;

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-autocomplete="list"
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck={false}
        className="h-11 w-full cursor-text rounded-lg border border-border bg-card pl-3.5 pr-10 text-base text-foreground outline-none transition-colors duration-150 placeholder:text-muted-foreground focus:border-primary/50 focus:ring-2 focus:ring-ring/25 md:h-10 md:text-sm"
        placeholder={open ? t("timezone.search") : t("timezone.unset")}
        value={inputValue}
        onFocus={() => {
          if (!open) openPicker();
        }}
        onClick={() => {
          if (!open) openPicker();
        }}
        onChange={(event) => {
          setQuery(event.target.value);
          setActive(0);
        }}
        onKeyDown={onKeyDown}
      />
      <ChevronDown
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-transform",
          open && "rotate-180",
        )}
      />

      {open ? (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-xl border border-border bg-card shadow-xl">
          {query.trim() === "" && value ? (
            <div className="px-3 pb-1 pt-2 text-xs text-muted-foreground">
              {t("timezone.current", { value })}
            </div>
          ) : null}

          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            aria-label={t("timezone.search")}
            className="max-h-64 overflow-y-auto overscroll-contain p-1"
          >
            {options.length === 0 ? (
              <li className="px-3 py-3 text-sm text-muted-foreground">{t("timezone.noMatch")}</li>
            ) : null}
            {options.map((zone, index) => {
              const selected = zone === value;
              const offset = zone ? timezoneOffsetLabel(zone) : "";
              return (
                <li
                  key={zone || "__none"}
                  id={`${listId}-${index}`}
                  data-index={index}
                  role="option"
                  aria-selected={selected}
                  className={cn(
                    "flex cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm",
                    index === active
                      ? "bg-accent text-accent-foreground"
                      : "text-foreground hover:bg-muted",
                  )}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => commit(zone)}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <Check
                      aria-hidden="true"
                      className={cn("h-4 w-4 shrink-0 text-primary", !selected && "invisible")}
                    />
                    <span className="truncate">{zone || t("common.none")}</span>
                  </span>
                  {offset ? (
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                      {offset}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>

          {query.trim() === "" ? (
            <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
              {t("timezone.hint")}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}