"use client";

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useI18n } from "@/lib/i18n";

export interface ExistingRecord {
  id: string;
  service_number: string | null;
  carrier: string | null;
  departure_time: string | null;
  departure_timezone: string | null;
  origin: string | null;
  destination: string | null;
}

interface DuplicateDialogProps {
  open: boolean;
  record: ExistingRecord | null;
  recordType: "flight" | "train" | "other";
  submitting?: boolean;
  onOpenExisting: () => void;
  onKeepNew: () => void;
  onCancel: () => void;
}

function formatDate(value: string, timeZone: string | null, locale: string): string {
  const options: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
  };
  try {
    return new Intl.DateTimeFormat(locale, {
      ...options,
      ...(timeZone ? { timeZone } : {}),
    }).format(new Date(value));
  } catch {
    return new Intl.DateTimeFormat(locale, options).format(new Date(value));
  }
}

export function DuplicateDialog({
  open,
  record,
  recordType,
  submitting,
  onOpenExisting,
  onKeepNew,
  onCancel,
}: DuplicateDialogProps) {
  const { t, locale } = useI18n();

  const serviceLabel =
    recordType === "flight"
      ? t("flights.serviceNumber")
      : recordType === "train"
        ? t("trains.serviceNumber")
        : t("transports.serviceNumber");
  const carrierLabel =
    recordType === "flight"
      ? t("flights.carrier")
      : recordType === "train"
        ? t("trains.carrier")
        : t("transports.carrier");

  const route =
    record?.origin && record?.destination
      ? `${record.origin} → ${record.destination}`
      : t("common.none");

  const date = record?.departure_time
    ? formatDate(record.departure_time, record.departure_timezone, locale)
    : t("common.none");

  return (
    <Modal open={open} onClose={onCancel} title={t("records.duplicateTitle")}>
      <div className="flex flex-col gap-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-warning/15 text-warning">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t("records.duplicateDescription")}
          </p>
        </div>

        {record ? (
          <dl className="grid grid-cols-3 gap-y-2 rounded-xl border border-border bg-background/50 p-4 text-sm">
            <dt className="text-muted-foreground">{serviceLabel}</dt>
            <dd className="col-span-2 font-medium">
              {record.service_number || t("common.none")}
            </dd>
            <dt className="text-muted-foreground">{t("flights.date")}</dt>
            <dd className="col-span-2 font-medium">{date}</dd>
            <dt className="text-muted-foreground">{t("flights.route")}</dt>
            <dd className="col-span-2 font-medium">{route}</dd>
            <dt className="text-muted-foreground">{carrierLabel}</dt>
            <dd className="col-span-2 font-medium">
              {record.carrier || t("common.none")}
            </dd>
          </dl>
        ) : null}

        <div className="flex flex-col gap-2">
          <Button onClick={onOpenExisting} disabled={submitting}>
            {t("records.duplicateOpenExisting")}
          </Button>
          <Button variant="outline" onClick={onKeepNew} disabled={submitting}>
            {t("records.duplicateKeepNew")}
          </Button>
          <Button variant="ghost" onClick={onCancel} disabled={submitting}>
            {t("common.cancel")}
          </Button>
        </div>
      </div>
    </Modal>
  );
}