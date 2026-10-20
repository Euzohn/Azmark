import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  actions?: React.ReactNode;
  backHref?: string;
  backLabel?: string;
  className?: string;
}

/**
 * Unified page header used across the app so every page opens with the same
 * rhythm: optional back link, optional eyebrow, display title, muted subtitle,
 * and a right-aligned actions slot. Replaces ad-hoc per-page header markup.
 */
export function PageHeader({
  title,
  subtitle,
  eyebrow,
  actions,
  backHref,
  backLabel,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn("flex animate-fade-in-up flex-col gap-3", className)}>
      {backHref ? (
        <Link
          href={backHref}
          className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {backLabel ?? "Back"}
        </Link>
      ) : null}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          {eyebrow ? (
            <div className="mb-2 text-[11px] font-medium tracking-[0.16em] text-muted-foreground/80">
              {eyebrow}
            </div>
          ) : null}
          <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {subtitle ? (
            <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        ) : null}
      </div>
    </div>
  );
}
