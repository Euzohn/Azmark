"use client";

import { X } from "lucide-react";
import { useEffect } from "react";

import { cn } from "@/lib/utils";

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function BottomSheet({ open, onClose, title, children, className }: BottomSheetProps) {
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
    <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="animate-fade-in absolute inset-0 cursor-default bg-black/40"
      />
      <div
        className={cn(
          "animate-sheet-up absolute inset-x-0 bottom-0 rounded-t-2xl border-t border-border bg-card shadow-2xl",
          className,
        )}
        style={{ paddingBottom: "calc(1.25rem + env(safe-area-inset-bottom))" }}
      >
        <div className="mx-auto mt-3 h-1 w-10 rounded-full bg-border" />
        <div className="flex items-center justify-between px-5 pb-2 pt-3">
          {title ? (
            <span className="font-display text-lg font-semibold tracking-tight">{title}</span>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex flex-col gap-1 px-3">{children}</div>
      </div>
    </div>
  );
}
