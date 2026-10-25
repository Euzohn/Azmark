"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";

type FabProps = {
  /** Accessible label (the FAB is icon-only). */
  label: string;
  /** Render as a Next `<Link>` to this destination. Mutually exclusive with `onClick`. */
  href?: string;
  onClick?: () => void;
  className?: string;
  children: React.ReactNode;
};

/**
 * Floating action button: the primary "add" affordance on list pages.
 *
 * Shown only below the `md` breakpoint — that's where the app's bottom nav is
 * fixed, so a scrolled user can still reach "add" without going back to the
 * top. It clears the nav with `bottom-28`, matching the layout's own `pb-28`.
 * On desktop the header add buttons stay and no FAB is shown, avoiding a
 * double affordance.
 *
 * Renders a `<button>` (with `onClick`, e.g. to open a sheet) or a Next
 * `<Link>` (with `href`, e.g. straight to /trips/new) so every list page can
 * share the exact same look and placement.
 */
export function Fab({ label, href, onClick, className, children }: FabProps) {
  const classes = cn(
    "fixed bottom-28 right-4 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/30 transition-transform duration-150 hover:scale-105 active:scale-95 md:hidden",
    className,
  );
  if (href) {
    return (
      <Link href={href} aria-label={label} className={classes}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" aria-label={label} onClick={onClick} className={classes}>
      {children}
    </button>
  );
}
