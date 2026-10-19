"use client";

import { AzmarkMark } from "@/components/azmark-mark";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  const { t } = useI18n();
  return (
    <div className={cn("mb-8 flex flex-col items-center gap-2.5 text-center", className)}>
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#252822] text-[#F5F1E8] shadow-lg shadow-black/20 dark:bg-[#F5F1E8] dark:text-[#252822]">
        <AzmarkMark className="h-8 w-auto" />
      </div>
      <div>
        <div className="font-display text-2xl font-semibold tracking-tight">{t("app.name")}</div>
        <div className="text-xs tracking-wide text-muted-foreground">{t("app.tagline")}</div>
      </div>
    </div>
  );
}
