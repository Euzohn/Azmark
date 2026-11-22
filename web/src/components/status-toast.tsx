"use client";

import { CheckCircle2, X } from "lucide-react";
import { useEffect } from "react";

import { useI18n } from "@/lib/i18n";
import { useStatusToast } from "@/lib/status-toast";

/**
 * One-time, auto-dismissing notice that overdue records were auto-completed by
 * the read-time status sweep. Mounted once in the app shell; sits above the
 * mobile bottom nav so it never covers navigation.
 */
export function StatusToast() {
  const { t } = useI18n();
  const count = useStatusToast((s) => s.count);
  const dismiss = useStatusToast((s) => s.dismiss);

  useEffect(() => {
    if (count === null) return;
    const id = setTimeout(dismiss, 6000);
    return () => clearTimeout(id);
  }, [count, dismiss]);

  if (count === null) return null;
  return (
    <div
      role="status"
      className="fixed bottom-24 right-4 z-[60] flex max-w-[calc(100vw-2rem)] items-center gap-2.5 rounded-xl border border-border bg-card px-4 py-3 text-sm shadow-lg animate-fade-in-up md:bottom-6 md:right-6"
    >
      <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />
      <span>
        {count === 1 ? t("toast.statusUpdatedOne") : t("toast.statusUpdated", { count })}
      </span>
      <button
        type="button"
        onClick={dismiss}
        aria-label={t("toast.dismiss")}
        className="ml-1 rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
