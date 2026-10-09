"use client";

import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface ComboboxOption {
  value: string;
  label: string;
  hint?: string;
  data?: Record<string, string>;
}

interface ComboboxProps {
  value: string;
  onChange: (value: string) => void;
  onSelect?: (option: ComboboxOption) => void;
  /** Must be memoized (useCallback) — it is an effect dependency. */
  fetchOptions: (query: string) => Promise<ComboboxOption[]>;
  placeholder?: string;
  emptyText?: string;
  minChars?: number;
  className?: string;
}

export function Combobox({
  value,
  onChange,
  onSelect,
  fetchOptions,
  placeholder,
  emptyText = "No matches",
  minChars = 1,
  className,
}: ComboboxProps) {
  const [draft, setDraft] = useState("");
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<ComboboxOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);

  // While closed the input mirrors the bound value; while open it shows the draft.
  const displayed = open ? draft : value;

  useEffect(() => {
    if (!open) return;
    const q = draft.trim();
    if (q.length < minChars) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      setLoading(true);
      fetchOptions(q)
        .then((result) => {
          if (cancelled) return;
          setOptions(result);
          setHighlight(result.length > 0 ? 0 : -1);
        })
        .catch(() => {
          if (!cancelled) setOptions([]);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [draft, open, minChars, fetchOptions]);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const choose = (option: ComboboxOption) => {
    setDraft(option.value);
    onChange(option.value);
    onSelect?.(option);
    setOpen(false);
  };

  const handleFocus = () => {
    setDraft(value);
    setOpen(true);
  };

  const handleChange = (next: string) => {
    setDraft(next);
    setOpen(true);
    if (next.trim().length < minChars) {
      setOptions([]);
      setHighlight(-1);
      setLoading(false);
    }
    if (next !== value) onChange(next);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open && (event.key === "ArrowDown" || event.key === "Enter")) {
      setOpen(true);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((prev) => Math.min(prev + 1, options.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((prev) => Math.max(prev - 1, 0));
    } else if (event.key === "Enter") {
      if (highlight >= 0 && options[highlight]) {
        event.preventDefault();
        choose(options[highlight]);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  const showEmpty =
    open && draft.trim().length >= minChars && !loading && options.length === 0;

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <Input
        value={displayed}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        onFocus={handleFocus}
        onChange={(event) => handleChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      {open && (options.length > 0 || showEmpty) ? (
        <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-border bg-card py-1 text-sm shadow-lg">
          {options.length === 0 ? (
            <li className="px-3 py-2 text-muted-foreground">{emptyText}</li>
          ) : (
            options.map((option, index) => (
              <li key={`${option.value}-${index}`}>
                <button
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(option)}
                  className={cn(
                    "flex w-full flex-col items-start px-3 py-2 text-left",
                    index === highlight ? "bg-muted" : "hover:bg-muted",
                  )}
                >
                  <span>{option.label}</span>
                  {option.hint ? (
                    <span className="text-xs text-muted-foreground">{option.hint}</span>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
