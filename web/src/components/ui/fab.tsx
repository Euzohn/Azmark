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
 * Visible on every breakpoint so a scrolled user can always reach "add"
 * without going back to the top. On `< md` it clears the fixed bottom nav
 * (`bottom-28`, matching the layout's own `pb-28`); on `md+` there is no
 * bottom nav, so it drops to `bottom-6`.
 *
 * Renders a `<button>` (with `onClick`, e.g. to open a sheet) or a Next
 * `<Link>` (with `href`, e.g. straight to /trips/new) so every list page can
 * share the exact same look and placement.
 */
export function Fab({ label, href, onClick, className, children }: FabProps) {
  const classes = cn(
    "fixed right-4 z-30 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg transition-colors hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:hidden",
    className,
  );
  if (href) {
    return (
      <Link href={href} aria-label={label} className={classes} style={{ bottom: "calc(6rem + env(safe-area-inset-bottom))" }}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" aria-label={label} onClick={onClick} className={classes} style={{ bottom: "calc(6rem + env(safe-area-inset-bottom))" }}>
      {children}
    </button>
  );
}
