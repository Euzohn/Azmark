"use client";

import { Languages } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

export function LanguageToggle() {
  const { locale, setLocale } = useI18n();

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setLocale(locale === "zh-CN" ? "en-US" : "zh-CN")}
      aria-label="Switch language"
    >
      <Languages className="h-4 w-4" />
      {locale === "zh-CN" ? "EN" : "中"}
    </Button>
  );
}
