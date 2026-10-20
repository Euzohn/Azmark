"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert, Users } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { AUDIT_ACTION_LABELS } from "@/lib/audit-actions";
import { useAuth } from "@/lib/auth-store";
import { useI18n, type TranslationKey } from "@/lib/i18n";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function AdminPage({ embedded = false }: { embedded?: boolean } = {}) {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "ADMIN";

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [logPage, setLogPage] = useState(1);

  const usersQuery = useQuery({
    queryKey: ["admin-users", search, page],
    queryFn: () => api.listAdminUsers({ search: search || undefined, page, page_size: 20 }),
    enabled: isAdmin,
  });

  const systemQuery = useQuery({
    queryKey: ["admin-system"],
    queryFn: api.getAdminSystem,
    enabled: isAdmin,
  });

  const logsQuery = useQuery({
    queryKey: ["admin-logs", logPage],
    queryFn: () => api.listAdminLogs({ page: logPage, page_size: 20 }),
    enabled: isAdmin,
  });

  const updateUser = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { role?: string; status?: string } }) =>
      api.updateAdminUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-system"] });
      queryClient.invalidateQueries({ queryKey: ["admin-logs"] });
    },
  });

  if (!user) {
    return <div className="text-muted-foreground">{t("common.loading")}</div>;
  }

  if (!isAdmin) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title={t("admin.noAccess")}
        hint={t("admin.noAccessHint")}
        className="py-20"
      />
    );
  }

  const users = usersQuery.data?.items ?? [];
  const userPages = Math.max(1, Math.ceil((usersQuery.data?.total ?? 0) / 20));
  const logPages = Math.max(1, Math.ceil((logsQuery.data?.total ?? 0) / 20));
  const system = systemQuery.data;

  const stats: { key: TranslationKey; value: number }[] = system
    ? [
        { key: "admin.stat.users", value: system.users },
        { key: "admin.stat.active", value: system.active_users },
        { key: "admin.stat.admins", value: system.admins },
        { key: "admin.stat.records", value: system.records },
        { key: "admin.stat.trips", value: system.trips },
        { key: "admin.stat.logs", value: system.audit_logs },
      ]
    : [];

  return (
    <div className="flex flex-col gap-6">
      {embedded ? null : (
        <div className="animate-fade-in-up">
          <h1 className="font-display text-3xl font-semibold tracking-tight">{t("admin.title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("admin.subtitle", { version: system?.version ?? "" })}
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((item, index) => (
          <div
            key={item.key}
            className="rounded-2xl border border-border bg-card px-4 py-3 animate-fade-in-up"
            style={{ animationDelay: `${index * 30}ms` }}
          >
            <div className="text-xs text-muted-foreground">{t(item.key)}</div>
            <div className="mt-1 font-display text-2xl font-semibold">{item.value}</div>
          </div>
        ))}
      </div>

      <Card className="animate-fade-in-up" style={{ animationDelay: "120ms" }}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            {t("admin.users")}
            {usersQuery.data ? (
              <Badge variant="neutral">{usersQuery.data.total}</Badge>
            ) : null}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <form
            className="flex flex-col gap-2 sm:flex-row sm:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              setPage(1);
              setSearch(searchInput.trim());
            }}
          >
            <div className="flex-1">
              <Label className="mb-1.5 block" htmlFor="admin-search">
                {t("common.search")}
              </Label>
              <Input
                id="admin-search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder={t("admin.searchPlaceholder")}
              />
            </div>
            <Button type="submit" variant="outline">
              {t("common.search")}
            </Button>
          </form>

          {updateUser.isError ? (
            <p className="text-sm text-danger">{t("admin.updateFailed")}</p>
          ) : null}

          {usersQuery.isLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 4 }, (_, index) => (
                <Skeleton key={index} className="h-12 w-full" />
              ))}
            </div>
          ) : null}

          {!usersQuery.isLoading && users.length === 0 ? (
            <EmptyState icon={Users} title={t("admin.empty")} />
          ) : null}

          {users.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-border">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="bg-muted/70 text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-semibold">{t("admin.username")}</th>
                    <th className="px-4 py-3 font-semibold">{t("admin.email")}</th>
                    <th className="px-4 py-3 font-semibold">{t("admin.role")}</th>
                    <th className="px-4 py-3 font-semibold">{t("admin.status")}</th>
                    <th className="px-4 py-3 font-semibold">{t("admin.records")}</th>
                    <th className="px-4 py-3 font-semibold">{t("admin.trips")}</th>
                    <th className="px-4 py-3 font-semibold">{t("admin.joined")}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((item) => {
                    const isSelf = item.id === user.id;
                    const pending = updateUser.isPending;
                    return (
                      <tr key={item.id} className="border-t border-border hover:bg-accent/40">
                        <td className="px-4 py-3">
                          <div className="font-medium">{item.display_name || item.username}</div>
                          <div className="text-xs text-muted-foreground">@{item.username}</div>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{item.email || "—"}</td>
                        <td className="px-4 py-3">
                          <Select
                            aria-label={t("admin.role")}
                            value={item.role}
                            disabled={isSelf || pending}
                            onChange={(event) =>
                              updateUser.mutate({
                                id: item.id,
                                data: { role: event.target.value },
                              })
                            }
                          >
                            <option value="USER">{t("admin.role.user")}</option>
                            <option value="ADMIN">{t("admin.role.admin")}</option>
                          </Select>
                        </td>
                        <td className="px-4 py-3">
                          <Select
                            aria-label={t("admin.status")}
                            value={item.status}
                            disabled={isSelf || pending}
                            onChange={(event) =>
                              updateUser.mutate({
                                id: item.id,
                                data: { status: event.target.value },
                              })
                            }
                          >
                            <option value="ACTIVE">{t("admin.status.active")}</option>
                            <option value="DISABLED">{t("admin.status.disabled")}</option>
                          </Select>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{item.records}</td>
                        <td className="px-4 py-3 text-muted-foreground">{item.trips}</td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatDate(item.created_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          {userPages > 1 ? (
            <div className="flex items-center justify-between gap-3">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                {t("common.previous")}
              </Button>
              <span className="text-xs text-muted-foreground">
                {t("common.pageOf", { page, pages: userPages })}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= userPages}
                onClick={() => setPage((current) => Math.min(userPages, current + 1))}
              >
                {t("common.next")}
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card className="animate-fade-in-up" style={{ animationDelay: "180ms" }}>
        <CardHeader>
          <CardTitle>{t("admin.logs")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {logsQuery.isLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 4 }, (_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : null}

          {!logsQuery.isLoading && (logsQuery.data?.items.length ?? 0) === 0 ? (
            <EmptyState title={t("admin.logsEmpty")} />
          ) : null}

          {logsQuery.data && logsQuery.data.items.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-border">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="bg-muted/70 text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-semibold">{t("audit.action")}</th>
                    <th className="px-4 py-3 font-semibold">{t("admin.logUser")}</th>
                    <th className="px-4 py-3 font-semibold">{t("audit.resource")}</th>
                    <th className="px-4 py-3 font-semibold">{t("audit.time")}</th>
                  </tr>
                </thead>
                <tbody>
                  {logsQuery.data.items.map((log) => {
                    const label = AUDIT_ACTION_LABELS[log.action];
                    return (
                      <tr key={log.id} className="border-t border-border hover:bg-accent/40">
                        <td className="px-4 py-3 font-medium">
                          {label ? t(label) : log.action}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                          {log.user_id ? log.user_id.slice(0, 8) : "—"}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {log.resource_type || "—"}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatDateTime(log.created_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          {logPages > 1 ? (
            <div className="flex items-center justify-between gap-3">
              <Button
                variant="outline"
                size="sm"
                disabled={logPage <= 1}
                onClick={() => setLogPage((current) => Math.max(1, current - 1))}
              >
                {t("common.previous")}
              </Button>
              <span className="text-xs text-muted-foreground">
                {t("common.pageOf", { page: logPage, pages: logPages })}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={logPage >= logPages}
                onClick={() => setLogPage((current) => Math.min(logPages, current + 1))}
              >
                {t("common.next")}
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
