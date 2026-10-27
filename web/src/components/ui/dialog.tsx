"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useRef } from "react";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  className?: string;
  variant?: "modal" | "sheet" | "responsive";
}

/** shadcn-style Radix dialog: portal, focus trap, scroll lock and focus restoration. */
export function Dialog({ open, onClose, title, children, className, variant = "modal" }: DialogProps) {
  const { t } = useI18n();
  const returnFocus = useRef<HTMLElement | null>(null);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/45 data-[state=open]:animate-fade-in" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          onOpenAutoFocus={() => { returnFocus.current = document.activeElement as HTMLElement | null; }}
          onCloseAutoFocus={(event) => { event.preventDefault(); returnFocus.current?.focus(); }}
          className={cn(
            "fixed z-50 flex flex-col border border-border bg-card text-foreground shadow-xl outline-none",
            variant === "modal"
              ? "left-1/2 top-1/2 max-h-[85dvh] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl"
              : "inset-x-0 bottom-0 max-h-[85dvh] rounded-t-2xl pb-[env(safe-area-inset-bottom)]",
            variant === "responsive" && "md:inset-x-auto md:bottom-auto md:left-1/2 md:top-1/2 md:w-[calc(100%-2rem)] md:max-w-md md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-xl md:pb-0",
            className,
          )}
        >
          <div className="flex shrink-0 items-center justify-between gap-4 border-b border-border px-5 py-4">
            <DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title>
            <DialogPrimitive.Close aria-label={t("common.close")} className="flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <X className="h-4 w-4" />
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 overflow-y-auto overscroll-contain p-5">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
