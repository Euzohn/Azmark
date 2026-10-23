"use client";

import { X } from "lucide-react";
import { useEffect } from "react";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  className?: string;
}

export function Modal({ open, onClose, title, children, className }: ModalProps) {
  const { t } = useI18n();

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label={t("common.close")}
        onClick={onClose}
        className="animate-fade-in absolute inset-0 cursor-default bg-black/50 backdrop-blur-[2px]"
      />
      <div
        className={cn(
          "animate-scale-in relative flex w-full max-w-md flex-col gap-4 rounded-2xl border border-border bg-card p-6 shadow-2xl",
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-lg font-semibold tracking-tight">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}