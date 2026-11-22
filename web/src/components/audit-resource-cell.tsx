"use client";

import { useI18n } from "@/lib/i18n";

/**
 * Resource cell shared by the user and admin audit tables. Most actions show
 * the raw resource type; the aggregated status-sweep row instead renders its
 * per-table counts (meta only carries counts — never row IDs or content).
 */
export function AuditResourceCell({
  action,
  resourceType,
  meta,
}: {
  action: string;
  resourceType: string | null;
  meta: Record<string, unknown> | null;
}) {
  const { t } = useI18n();
  if (action === "status_auto_advanced") {
    const counts = meta?.counts as Record<string, number> | undefined;
    if (counts) {
      const parts: string[] = [];
      if (counts.transport) parts.push(t("audit.statusTransport", { count: counts.transport }));
      if (counts.hotel) parts.push(t("audit.statusHotel", { count: counts.hotel }));
      if (counts.trip) parts.push(t("audit.statusTrip", { count: counts.trip }));
      if (parts.length > 0) return <>{parts.join(" · ")}</>;
    }
  }
  return <>{resourceType || "—"}</>;
}
