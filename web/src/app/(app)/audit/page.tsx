"use client";

import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";

const ACTION_LABELS: Record<string, TranslationKey> = {
  login: "audit.action.login",
  login_failed: "audit.action.login_failed",
  register: "audit.action.register",
  password_change: "audit.action.password_change",
  username_change: "audit.action.username_change",
  account_change: "audit.action.account_change",
  create_record: "audit.action.create_record",
  update_record: "audit.action.update_record",
  delete_record: "audit.action.delete_record",
};

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function AuditPage() {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["audit"],
    queryFn: () => api.listAuditLogs(),
  });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-display text-3xl font-semibold tracking-tight">{t("audit.title")}</h1>

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
        <div className="overflow-x-auto rounded-2xl border border-border bg-card">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/70 text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-5 py-3 font-semibold">{t("audit.action")}</th>
                <th className="px-5 py-3 font-semibold">{t("audit.resource")}</th>
                <th className="px-5 py-3 font-semibold">{t("audit.time")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((log) => {
                const label = ACTION_LABELS[log.action];
                return (
                  <tr key={log.id} className="border-t border-border transition-colors hover:bg-muted/40">
                    <td className="px-5 py-3 font-medium">{label ? t(label) : log.action}</td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {log.resource_type ? `${log.resource_type}` : "-"}
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {formatDateTime(log.created_at)}
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
