"use client";

import { useEffect } from "react";

/**
 * Keep ``document.title`` in sync with the current page so browser tabs,
 * history entries and screen readers announce where the user is (spec #95).
 * Pass an already translated label; the brand suffix is appended.
 */
export function usePageTitle(title: string | null | undefined): void {
  useEffect(() => {
    // `undefined` means "this component does not own the title" (e.g. an
    // embedded panel) — leave whatever the owning page set untouched.
    if (title === undefined || title === null) return;
    document.title = `${title} · Azmark`;
  }, [title]);
}