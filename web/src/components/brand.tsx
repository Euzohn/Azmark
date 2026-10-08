"use client";

import { Plane } from "lucide-react";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  const { t } = useI18n();
  return (
    <div className={cn("mb-6 flex flex-col items-center gap-2 text-center", className)}>
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
        <Plane className="h-5 w-5" />
      </div>
      <div>
        <div className="text-lg font-semibold tracking-tight">{t("app.name")}</div>
        <div className="text-xs text-muted-foreground">{t("app.tagline")}</div>
      </div>
    </div>
  );
}
