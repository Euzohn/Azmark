"use client";

import { Download, Paperclip, Plus, Receipt, StickyNote } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Attachment, TripDetail } from "@/lib/types";

const RESOURCE_PATHS: Record<string, string> = {
  flight: "/flights",
  train: "/trains",
  transport: "/transports",
};

const RESOURCE_LABELS = {
  flight: "attachments.resource.flight",
  train: "attachments.resource.train",
  transport: "attachments.resource.transport",
} as const;

const MAX_VISIBLE = 5;

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function SectionHeader({
  icon,
  title,
  hint,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
          {icon}
        </span>
        <div>
          <h2 className="font-display text-base font-semibold tracking-tight">{title}</h2>
          {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
        </div>
      </div>
      {action}
    </div>
  );
}

export function TripExtras({ trip }: { trip: TripDetail }) {
  const { t, locale } = useI18n();
  const pathname = usePathname();
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const summary = trip.expense_summary;
  const expenses = trip.expenses ?? [];
  const notes = trip.notes ?? [];
  const attachments = trip.attachments ?? [];
  const returnTo = encodeURIComponent(pathname);
  const addExpenseHref = `/expenses/new?trip_id=${trip.id}&return_to=${returnTo}`;
  const addNoteHref = `/notes/new?trip_id=${trip.id}&return_to=${returnTo}`;

  const download = async (attachment: Attachment) => {
    setError(null);
    setDownloading(attachment.id);
    try {
      saveBlob(await api.downloadAttachment(attachment.id), attachment.filename);
    } catch {
      setError(t("attachments.downloadFailed"));
    } finally {
      setDownloading(null);
    }
  };

  // The expenses page reads `trip_id` from the URL, so this is a real filter,
  // not a blind link to the unfiltered list.

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="overflow-hidden rounded-xl border border-border bg-card">
          <SectionHeader
            icon={<Receipt className="h-4 w-4" />}
            title={t("trips.expenses")}
            hint={
              summary
                ? summary.unconverted_count > 0
                  ? t("trips.expensesUnconverted", {
                      count: summary.unconverted_count,
                      currencies: summary.unconverted.map((item) => item.currency).join(" / "),
                    })
                  : t("trips.expensesConverted", {
                      amount: summary.converted_total,
                      currency: summary.report_currency,
                    })
                : undefined
            }
            action={
              <Link href={addExpenseHref}>
                <Button variant="outline" size="sm">
                  <Plus className="h-4 w-4" />
                  {t("expenses.add")}
                </Button>
              </Link>
            }
          />
          {summary && summary.converted_count === 0 && summary.unconverted_count > 0 ? (
            <p className="border-b border-border px-5 py-3 text-xs text-muted-foreground">
              {t("trips.expensesAllUnconverted")}
            </p>
          ) : null}
          {expenses.length === 0 ? (
            <p className="px-5 py-6 text-sm text-muted-foreground">{t("expenses.linkedEmpty")}</p>
          ) : (
            <ul className="divide-y divide-border">
              {expenses.slice(0, MAX_VISIBLE).map((expense) => (
                <li key={expense.id}>
                  <Link
                    href={`/expenses/${expense.id}?from=${encodeURIComponent(pathname)}`}
                    className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        {expense.description || t(`expenses.category.${expense.category}`)}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {t(`expenses.category.${expense.category}`)}
                        {expense.occurred_at
                          ? ` · ${new Date(expense.occurred_at).toLocaleDateString(locale, {
                              month: "short",
                              day: "numeric",
                            })}`
                          : ""}
                      </div>
                    </div>
                    <span className="shrink-0 text-sm font-semibold tabular-nums">
                      {expense.amount} {expense.currency}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {expenses.length > MAX_VISIBLE ? (
            <div className="border-t border-border px-5 py-3">
              <Link
                href={`/expenses?trip_id=${trip.id}`}
                className="text-xs font-medium text-primary hover:underline"
              >
                {t("common.viewAll")}
              </Link>
            </div>
          ) : null}
        </section>

        <section className="overflow-hidden rounded-xl border border-border bg-card">
          <SectionHeader
            icon={<StickyNote className="h-4 w-4" />}
            title={t("trips.notes")}
            hint={notes.length > 0 ? t("trips.notesCount", { count: notes.length }) : undefined}
            action={
              <Link href={addNoteHref}>
                <Button variant="outline" size="sm">
                  <Plus className="h-4 w-4" />
                  {t("notes.add")}
                </Button>
              </Link>
            }
          />
          {notes.length === 0 ? (
            <p className="px-5 py-6 text-sm text-muted-foreground">{t("trips.notesEmpty")}</p>
          ) : (
            <ul className="divide-y divide-border">
              {notes.slice(0, MAX_VISIBLE).map((note) => (
                <li key={note.id}>
                  <Link
                    href={`/notes/${note.id}?from=${returnTo}`}
                    className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{note.title}</div>
                      <div className="mt-0.5 truncate text-xs text-muted-foreground">
                        {note.content || t("notes.empty")}
                      </div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <SectionHeader
          icon={<Paperclip className="h-4 w-4" />}
          title={t("trips.attachments")}
          hint={t("trips.attachmentsHint")}
        />
        {error ? <p className="px-5 pt-3 text-sm text-danger">{error}</p> : null}
        {attachments.length === 0 ? (
          <p className="px-5 py-6 text-sm text-muted-foreground">
            {t("trips.attachmentsEmpty")}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {attachments.map((attachment) => {
              const base = RESOURCE_PATHS[attachment.resource_type];
              return (
                <li
                  key={attachment.id}
                  className="flex items-center gap-3 px-5 py-3"
                >
                  <Paperclip className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{attachment.filename}</p>
                    <p className="text-xs text-muted-foreground">
                      {base ? (
                        <Link
                          href={`${base}/${attachment.resource_id}`}
                          className="hover:underline"
                        >
                          {t(
                            RESOURCE_LABELS[
                              attachment.resource_type as keyof typeof RESOURCE_LABELS
                            ] ?? "attachments.title",
                          )}
                        </Link>
                      ) : (
                        attachment.resource_type
                      )}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    disabled={downloading === attachment.id}
                    onClick={() => void download(attachment)}
                    title={t("attachments.download")}
                    aria-label={t("attachments.download")}
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
