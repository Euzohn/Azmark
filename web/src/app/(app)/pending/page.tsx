"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, ClipboardCheck, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { usePageTitle } from "@/lib/page-title";
import type { PendingAction, PendingActionStatus } from "@/lib/types";

type Filter = "all" | "pending" | "resolved";

const STATUS_VARIANT: Record<
  PendingActionStatus,
  "neutral" | "warning" | "success" | "danger"
> = {
  pending: "warning",
  confirmed: "success",
  rejected: "neutral",
  failed: "danger",
  expired: "neutral",
};

const RECORD_PATH: Record<string, string> = {
  flight: "/flights",
  train: "/trains",
  other: "/transports",
  hotel: "/hotels",
  trip: "/trips",
  expense: "/expenses",
  note: "/notes",
  place: "/places",
  activity: "/activities",
};

function formatDateTime(value: string | null, locale: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
}

function ActionCard({
  action,
  locale,
  onConfirm,
  onReject,
}: {
  action: PendingAction;
  locale: string;
  onConfirm: (action: PendingAction) => void;
  onReject: (action: PendingAction) => void;
}) {
  const { t } = useI18n();
  const isPending = action.status === "pending";

  return (
    <Card className="animate-fade-in-up">
      <CardContent className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="neutral">{action.record_type}</Badge>
              <Badge variant={STATUS_VARIANT[action.status]}>
                {t(`pending.${action.status}`)}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {action.action === "create" ? "＋" : "✎"}
              </span>
            </div>
            <p className="mt-2 text-sm font-medium text-foreground">{action.summary}</p>
          </div>
          {isPending ? (
            <div className="flex shrink-0 items-center gap-2">
              <Button size="sm" onClick={() => onConfirm(action)}>
                <Check className="h-4 w-4" />
                {t("pending.confirm")}
              </Button>
              <Button size="sm" variant="outline" onClick={() => onReject(action)}>
                <X className="h-4 w-4" />
                {t("pending.reject")}
              </Button>
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {action.token_name ? (
            <span>
              {t("pending.fromAgent")} · {action.token_name}
            </span>
          ) : null}
          <span>
            {t("pending.created")} · {formatDateTime(action.created_at, locale)}
          </span>
          <span>
            {t("pending.expires")} ·{" "}
            {action.expires_at
              ? formatDateTime(action.expires_at, locale)
              : t("pending.neverExpires")}
          </span>
        </div>

        {action.status === "failed" && action.error ? (
          <p className="flex items-start gap-2 rounded-lg bg-danger/10 p-3 text-xs text-danger">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="break-all">
              {t("pending.failedHint")}
              {action.error}
            </span>
          </p>
        ) : null}

        {action.status === "confirmed" && action.result ? (
          <Link
            href={`${RECORD_PATH[action.record_type]}/${action.result.record_id}`}
            className="inline-flex w-fit items-center gap-1 text-xs text-primary transition-colors hover:underline"
          >
            {t("pending.viewRecord")}
          </Link>
        ) : null}
      </CardContent>
    </Card>
  );
}

export default function PendingActionsPage() {
  const { t, locale } = useI18n();
  usePageTitle(t("nav.pending"));
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("pending");
  const [duplicateId, setDuplicateId] = useState<string | null>(null);

  // "resolved" is a client-side pseudo-filter: the backend has no such status,
  // so it pulls everything and hides pending rows below.
  const queryStatus = filter === "all" ? undefined : filter === "pending" ? "pending" : undefined;

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["pending-actions", filter],
    queryFn: () => api.listPendingActions({ status: queryStatus }),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["pending-actions"] });

  const confirm = useMutation({
    mutationFn: ({ id, force }: { id: string; force: boolean }) =>
      api.confirmPendingAction(id, force),
    onSuccess: () => {
      setDuplicateId(null);
      void refresh();
    },
    onError: (err, vars) => {
      if (err instanceof ApiError && err.status === 409 && !vars.force) {
        setDuplicateId(vars.id);
        return;
      }
      setDuplicateId(null);
    },
  });

  const reject = useMutation({
    mutationFn: (id: string) => api.rejectPendingAction(id),
    onSuccess: () => void refresh(),
  });

  const items = (data?.items ?? []).filter((item) =>
    filter === "resolved" ? item.status !== "pending" : true,
  );

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <PageHeader
        title={t("pending.title")}
        subtitle={t("pending.subtitle")}
        actions={
          data ? (
            <span className="text-sm text-muted-foreground">
              {data.pending_total} {t("pending.pending")}
            </span>
          ) : null
        }
      />

      <Segmented<Filter>
        value={filter}
        onChange={setFilter}
        options={[
          { value: "pending", label: t("pending.filterPending") },
          { value: "resolved", label: t("pending.filterResolved") },
          { value: "all", label: t("pending.filterAll") },
        ]}
      />

      {isError ? (
        <EmptyState
          icon={ClipboardCheck}
          title={t("common.error")}
          action={
            <Button variant="outline" size="sm" onClick={() => void refetch()}>
              {t("common.retry")}
            </Button>
          }
        />
      ) : isLoading ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon={ClipboardCheck} title={t("pending.empty")} />
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((action) => (
            <ActionCard
              key={action.id}
              action={action}
              locale={locale}
              onConfirm={(a) => {
                setDuplicateId(null);
                confirm.mutate({ id: a.id, force: false });
              }}
              onReject={(a) => reject.mutate(a.id)}
            />
          ))}
        </div>
      )}

      <Dialog
        open={Boolean(duplicateId)}
        onClose={() => {
          if (!confirm.isPending) setDuplicateId(null);
        }}
        title={t("pending.duplicateTitle")}
        variant="responsive"
      >
        <p className="text-sm text-muted-foreground">{t("pending.duplicateHint")}</p>
        {confirm.isError ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {t("common.error")}
          </p>
        ) : null}
        <div className="mt-6 flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={confirm.isPending}
            onClick={() => setDuplicateId(null)}
          >
            {t("common.cancel")}
          </Button>
          <Button
            type="button"
            variant="danger"
            disabled={confirm.isPending}
            onClick={() => {
              if (duplicateId) confirm.mutate({ id: duplicateId, force: true });
            }}
          >
            {confirm.isPending ? t("pending.confirming") : t("pending.forceCreate")}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}