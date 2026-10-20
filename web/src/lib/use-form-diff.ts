import { useMemo } from "react";

type FieldKey<T> = Extract<keyof T, string>;

/**
 * Live diff between a form's current values and the baseline it was loaded
 * from. Shared by the trip / flight / train / transport edit forms so "what
 * will change" reads the same everywhere before the user saves.
 *
 * `skip` lists derived keys that must not be counted on their own (the IATA
 * code a carrier selection fills in next to the carrier name, for example) —
 * pass a module-level constant, not an inline array, so the memo stays stable.
 */
export function useFormDiff<T extends Record<string, string>>(
  form: T,
  baseline: T,
  labels: Partial<Record<FieldKey<T>, string>> = {},
  skip: readonly FieldKey<T>[] = [],
) {
  const changed = useMemo(() => {
    const found = new Set<FieldKey<T>>();
    (Object.keys(form) as FieldKey<T>[]).forEach((key) => {
      if (skip.includes(key)) return;
      if (form[key].trim() !== baseline[key].trim()) found.add(key);
    });
    return found;
  }, [form, baseline, skip]);

  const changedLabels = useMemo(
    () => [...changed].map((key) => labels[key] ?? key),
    [changed, labels],
  );

  return { changed, changedLabels };
}
