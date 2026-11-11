"use client";

import { Languages } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

export function LanguageToggle({
  compact = false,
  className,
}: {
  compact?: boolean;
  className?: string;
}) {
  const { locale, setLocale, t } = useI18n();
  const label = t("common.switchLanguage");

  return (
    <Button
      variant="ghost"
      size={compact ? "icon" : "sm"}
      onClick={() => setLocale(locale === "zh-CN" ? "en-US" : "zh-CN")}
      title={label}
      aria-label={label}
      className={className}
    >
      <Languages className="h-4 w-4" />
      {compact ? null : locale === "zh-CN" ? "EN" : "中"}
    </Button>
  );
}
