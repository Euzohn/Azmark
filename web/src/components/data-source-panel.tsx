"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { DataSource } from "@/lib/types";

function formatDateTime(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Provenance panel (spec #22/#37): lists where the user's external data came
 * from — flight lookups and CSV/JSON imports — so it is traceable. Rows are
 * user-scoped; each can be removed without touching the underlying records.
 */
export function DataSourcePanel() {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<DataSource | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["data-sources"],
    queryFn: () => api.listDataSources({ limit: 100 }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteDataSource(id),
    onSuccess: () => {
      setPendingDelete(null);
      void queryClient.invalidateQueries({ queryKey: ["data-sources"] });
    },
  });

  const typeLabel = (type: string): string =>
    type === "api" ? t("data.sourcesType.api")
    : type === "import" ? t("data.sourcesType.import")
    : type;

  return (
    <Card className="animate-fade-in-up" style={{ animationDelay: "150ms" }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DatabaseZap className="h-4 w-4" />
          {t("data.sources")}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">{t("data.sourcesHint")}</p>

        {isLoading ? (
          <div className="overflow-hidden rounded-lg border border-border">
            {Array.from({ length: 3 }, (_, index) => (
              <div
                key={index}
                className="flex items-center gap-4 border-b border-border px-4 py-3 last:border-b-0"
              >
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-24" />
              </div>
            ))}
          </div>
        ) : null}

        {data && data.items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-4 py-8 text-center">
            <DatabaseZap className="h-8 w-8 text-muted-foreground/60" />
            <p className="text-sm font-medium text-muted-foreground">{t("data.sourcesEmpty")}</p>
            <p className="text-xs text-muted-foreground">{t("data.sourcesEmptyHint")}</p>
          </div>
        ) : null}

        {data && data.items.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="bg-muted/70 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">{t("data.sourcesType")}</th>
                  <th className="px-4 py-2.5 font-semibold">{t("data.sourcesName")}</th>
                  <th className="px-4 py-2.5 font-semibold">{t("data.sourcesProvider")}</th>
                  <th className="px-4 py-2.5 font-semibold">{t("data.sourcesConfidence")}</th>
                  <th className="px-4 py-2.5 font-semibold">{t("data.sourcesTime")}</th>
                  <th className="px-4 py-2.5" aria-hidden />
                </tr>
              </thead>
              <tbody>
                {data.items.map((source) => (
                  <tr key={source.id} className="border-t border-border transition-colors hover:bg-accent/50">
                    <td className="px-4 py-3">
                      <Badge variant={source.source_type === "api" ? "primary" : "neutral"}>
                        {typeLabel(source.source_type)}
                      </Badge>
                    </td>
                    <td className="max-w-60 truncate px-4 py-3 font-medium" title={source.source_name}>
                      {source.source_name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{source.provider ?? "—"}</td>
                    <td className="px-4 py-3 tabular-nums text-muted-foreground">
                      {source.confidence !== null && source.confidence !== undefined
                        ? `${Math.round(source.confidence * 100)}%`
                        : "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">
                      {formatDateTime(source.retrieved_at, locale)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={t("data.sourcesDelete")}
                        onClick={() => setPendingDelete(source)}
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </CardContent>

      <Dialog
        open={pendingDelete !== null}
        onClose={() => {
          if (!remove.isPending) setPendingDelete(null);
        }}
        title={t("common.confirmDelete")}
        variant="responsive"
      >
        <p className="text-sm text-muted-foreground">{t("data.sourcesDeleteConfirm")}</p>
        {remove.isError ? (
          <p role="alert" className="mt-3 text-sm text-danger">{t("common.error")}</p>
        ) : null}
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="outline"
            disabled={remove.isPending}
            onClick={() => setPendingDelete(null)}
          >
            {t("common.cancel")}
          </Button>
          <Button
            variant="danger"
            disabled={remove.isPending}
            onClick={() => {
              if (pendingDelete) remove.mutate(pendingDelete.id);
            }}
          >
            {t(remove.isPending ? "common.loading" : "common.delete")}
          </Button>
        </div>
      </Dialog>
    </Card>
  );
}
