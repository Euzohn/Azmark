"use client";

import { Compass } from "lucide-react";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  const { t } = useI18n();
  return (
    <div className={cn("mb-8 flex flex-col items-center gap-2.5 text-center", className)}>
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-[#c26b30] to-primary text-primary-foreground shadow-lg shadow-primary/25">
        <Compass className="h-7 w-7" strokeWidth={1.75} />
      </div>
      <div>
        <div className="font-display text-2xl font-semibold tracking-tight">{t("app.name")}</div>
        <div className="text-xs tracking-wide text-muted-foreground">{t("app.tagline")}</div>
      </div>
    </div>
  );
}
