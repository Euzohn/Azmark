/**
 * One-time toast for the read-time status sweep (scheduled → completed).
 *
 * Parallel queries on page load each report their own X-Status-Updated total;
 * notifyStatusUpdate aggregates them within a short window so the user sees a
 * single toast instead of a stack. The backend only sends non-zero totals when
 * it actually changed rows, so this naturally fires once per batch of changes.
 */
import { create } from "zustand";

interface StatusToastState {
  count: number | null;
  show: (count: number) => void;
  dismiss: () => void;
}

export const useStatusToast = create<StatusToastState>((set) => ({
  count: null,
  show: (count) => set({ count }),
  dismiss: () => set({ count: null }),
}));

const AGGREGATE_WINDOW_MS = 600;

let pending = 0;
let timer: ReturnType<typeof setTimeout> | null = null;

export function notifyStatusUpdate(count: number): void {
  if (!Number.isFinite(count) || count <= 0) return;
  pending += count;
  if (timer !== null) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    const total = pending;
    pending = 0;
    useStatusToast.getState().show(total);
  }, AGGREGATE_WINDOW_MS);
}

/** Reset aggregation state (tests only). */
export function resetStatusToast(): void {
  if (timer !== null) clearTimeout(timer);
  timer = null;
  pending = 0;
  useStatusToast.getState().dismiss();
}
