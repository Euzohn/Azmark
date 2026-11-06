"use client";

import { useSyncExternalStore } from "react";

export type TimelineDirection = "asc" | "desc";

const key = "azmark-timeline-direction";
const listeners = new Set<() => void>();
let cached: TimelineDirection | null = null;

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function snapshot(): TimelineDirection {
  if (cached === null) {
    try {
      cached = window.localStorage.getItem(key) === "desc" ? "desc" : "asc";
    } catch {
      cached = "asc";
    }
  }
  return cached;
}

export function useTimelineDirection() {
  const direction = useSyncExternalStore(subscribe, snapshot, () => "asc" as const);
  const setDirection = (next: TimelineDirection) => {
    cached = next;
    try { window.localStorage.setItem(key, next); } catch { /* preference stays in memory */ }
    for (const listener of listeners) listener();
  };
  return [direction, setDirection] as const;
}
