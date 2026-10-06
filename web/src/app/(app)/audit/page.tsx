"use client";

import { useQuery } from "@tanstack/react-query";

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
      <h1 className="text-xl font-semibold">{t("audit.title")}</h1>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : null}

      {data && data.items.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">{t("audit.empty")}</p>
      ) : null}

      {data && data.items.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">{t("audit.action")}</th>
                <th className="px-4 py-2 font-medium">{t("audit.resource")}</th>
                <th className="px-4 py-2 font-medium">{t("audit.time")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((log) => {
                const label = ACTION_LABELS[log.action];
                return (
                  <tr key={log.id} className="border-t border-border">
                    <td className="px-4 py-2">{label ? t(label) : log.action}</td>
                    <td className="px-4 py-2 text-muted-foreground">
                      {log.resource_type ? `${log.resource_type}` : "—"}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">
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
