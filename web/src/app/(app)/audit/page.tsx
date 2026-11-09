"use client";

import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { AUDIT_ACTION_LABELS } from "@/lib/audit-actions";
import { useI18n } from "@/lib/i18n";
import type { AuditLog } from "@/lib/types";

function formatDateTime(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Shorten a tracing token (ip hash / request id) to a stable, copy-friendly prefix. */
function shortToken(value: string | null | undefined, length = 8): string {
  return value ? value.slice(0, length) : "—";
}

/**
 * One cell combining the tracing signals (spec #47): the raw client IP, the
 * sanitised client hint and the request correlation id. The raw address is shown
 * for self-hosted traceability; the UA is already sanitised server-side.
 */
function AuditClientCell({ log }: { log: AuditLog }) {
  const { t } = useI18n();
  const ua = log.user_agent;
  return (
    <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
      <span className="font-mono" title={t("audit.ip")}>
        <span className="text-muted-foreground/70">{t("audit.ipShort")}</span>{" "}
        {log.ip || "—"}
      </span>
      {ua ? (
        <span className="max-w-[220px] truncate" title={ua}>
          {ua}
        </span>
      ) : null}
      {log.request_id ? (
        <span className="font-mono text-[10px] text-muted-foreground/60" title={log.request_id}>
          <span className="text-muted-foreground/50">{t("audit.request")}</span>{" "}
          {shortToken(log.request_id, 12)}
        </span>
      ) : null}
    </div>
  );
}

export default function AuditPage({ embedded = false }: { embedded?: boolean } = {}) {
  const { t, locale } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["audit"],
    queryFn: () => api.listAuditLogs(),
  });

  return (
    <div className="flex flex-col gap-4">
      {embedded ? null : (
        <h1 className="font-display text-3xl font-semibold tracking-tight animate-fade-in-up">{t("audit.title")}</h1>
      )}

      {isLoading ? (
        <div className="overflow-hidden rounded-2xl border border-border bg-card">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index} className="flex items-center gap-4 border-b border-border px-4 py-3">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 flex-1" />
            </div>
          ))}
        </div>
      ) : null}

      {data && data.items.length === 0 ? (
        <EmptyState
          icon={History}
          title={t("audit.empty")}
          hint={t("audit.emptyHint")}
        />
      ) : null}

      {data && data.items.length > 0 ? (
        <div className="overflow-x-auto rounded-2xl border border-border bg-card animate-fade-in-up">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-muted/70 text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-5 py-3 font-semibold">{t("audit.action")}</th>
                <th className="px-5 py-3 font-semibold">{t("audit.resource")}</th>
                <th className="px-5 py-3 font-semibold">{t("audit.client")}</th>
                <th className="px-5 py-3 font-semibold">{t("audit.time")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((log, index) => {
                const label = AUDIT_ACTION_LABELS[log.action];
                return (
                  <tr key={log.id} className="border-t border-border transition-colors hover:bg-accent/50" style={{ animationDelay: `${index * 20}ms` }}>
                    <td className="px-5 py-3 font-medium">{label ? t(label) : log.action}</td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {log.resource_type ? `${log.resource_type}` : "-"}
                    </td>
                    <td className="px-5 py-3">
                      <AuditClientCell log={log} />
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {formatDateTime(log.created_at, locale)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
