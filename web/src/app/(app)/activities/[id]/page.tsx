"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, MapPin, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { ActivityForm } from "@/components/activity-form";
import { PageHeader } from "@/components/page-header";
import { TripLinkCard } from "@/components/trip-link-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Activity, ActivityInput } from "@/lib/types";

function formatDateTime(value: string | null, locale: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ActivityDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t, locale } = useI18n();
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [saved, setSaved] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["activity", id],
    queryFn: () => api.getActivity(id),
    enabled: Boolean(id),
  });

  const { data: place } = useQuery({
    queryKey: ["place", data?.place_id],
    queryFn: () => api.getPlace(data!.place_id!),
    enabled: Boolean(data?.place_id),
  });

  const update = useMutation({
    mutationFn: (input: ActivityInput) => api.updateActivity(id, input),
    onSuccess: async (activity) => {
      queryClient.setQueryData(["activity", id], activity);
      setDirty(false);
      setEditing(false);
      setSaved(true);
      await Promise.all(
        ["activities", "activity", "trips", "trip", "dashboard"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteActivity(id),
    onSuccess: async () => {
      await Promise.all(
        ["activities", "activity", "trips", "trip", "dashboard"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
      router.replace("/activities");
    },
  });

  const cancel = () => {
    if (dirty && !window.confirm(t("common.unsaved"))) return;
    setDirty(false);
    setEditing(false);
    update.reset();
  };

  if (isLoading) return <DetailSkeleton />;
  if (isError) {
    return (
      <div role="alert" className="flex items-center gap-4">
        <p className="text-sm text-danger">{t("common.error")}</p>
        <Button variant="outline" onClick={() => void refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }
  if (!data) return <p>{t("common.empty")}</p>;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={t(editing ? "activities.edit" : "activities.detail")}
        backHref="/activities"
        backLabel={t("common.back")}
        actions={
          editing ? undefined : (
            <>
              <Button
                variant="outline"
                onClick={() => {
                  setSaved(false);
                  setEditing(true);
                }}
              >
                <Pencil className="h-4 w-4" />
                {t("common.edit")}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("common.actions")}
                onClick={() => setMoreOpen(true)}
              >
                <MoreHorizontal className="h-5 w-5" />
              </Button>
            </>
          )
        }
      />
      {saved && !editing ? (
        <p role="status" className="text-sm text-success">
          {t("common.saved")}
        </p>
      ) : null}

      {editing ? (
        <>
          {update.isError ? (
            <p role="alert" className="text-sm text-danger">
              {t("common.error")}
            </p>
          ) : null}
          <ActivityForm
            initial={data}
            submitting={update.isPending}
            onDirtyChange={setDirty}
            onCancel={cancel}
            onSubmit={(input) => update.mutate(input)}
          />
        </>
      ) : (
        <>
          <ActivitySummary activity={data} locale={locale} />
          {place ? (
            <Link
              href={`/places/${place.id}`}
              className="flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-4 transition-colors hover:bg-muted/50"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <MapPin className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <div className="text-xs text-muted-foreground">{t("activities.place")}</div>
                <div className="truncate text-sm font-medium">{place.name}</div>
              </div>
            </Link>
          ) : null}
          {data.trip_id ? (
            <TripLinkCard tripId={data.trip_id} label={t("activities.trip")} />
          ) : null}
        </>
      )}

      <Dialog
        open={moreOpen}
        onClose={() => setMoreOpen(false)}
        title={t("common.actions")}
        variant="responsive"
      >
        <Button
          variant="ghost"
          className="w-full justify-start text-danger"
          onClick={() => {
            setMoreOpen(false);
            setDeleteOpen(true);
          }}
        >
          <Trash2 className="h-4 w-4" />
          {t("common.delete")}
        </Button>
      </Dialog>
      <Dialog
        open={deleteOpen}
        onClose={() => {
          if (!remove.isPending) setDeleteOpen(false);
        }}
        title={t("common.confirmDelete")}
        variant="responsive"
      >
        <p className="text-sm text-muted-foreground">{t("activities.deleteConfirm")}</p>
        {remove.isError ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {t("common.error")}
          </p>
        ) : null}
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="outline"
            disabled={remove.isPending}
            onClick={() => setDeleteOpen(false)}
          >
            {t("common.cancel")}
          </Button>
          <Button variant="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
            {t(remove.isPending ? "common.loading" : "common.delete")}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

function ActivitySummary({ activity, locale }: { activity: Activity; locale: string }) {
  const { t } = useI18n();
  const fields: [TranslationKey, string | null][] = [
    ["activities.type", t(`activities.type.${activity.type}`)],
    ["activities.startAt", formatDateTime(activity.start_at, locale)],
    ["activities.endAt", formatDateTime(activity.end_at, locale)],
    [
      "activities.price",
      activity.price ? `${activity.price} ${activity.currency ?? ""}`.trim() : null,
    ],
    ["activities.notes", activity.notes],
  ];

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 md:px-7">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <CalendarDays className="h-4 w-4" strokeWidth={1.75} />
          </span>
          <div className="min-w-0">
            <div className="font-display text-lg font-semibold tracking-tight">
              {activity.name}
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">
              {formatDateTime(activity.start_at, locale)}
            </div>
          </div>
        </div>
        <Badge variant="neutral">{t(`activities.type.${activity.type}`)}</Badge>
      </div>
      <dl className="grid gap-x-6 gap-y-3 px-5 py-5 sm:grid-cols-2 md:px-7">
        {fields.map(([key, value]) => (
          <div key={key} className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {t(key)}
            </dt>
            <dd className="text-sm text-foreground">{value || "—"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function DetailSkeleton() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Skeleton className="h-12 w-64" />
      <Skeleton className="h-52 w-full rounded-xl" />
    </div>
  );
}

export default function ActivityDetailPage() {
  return <ActivityDetail />;
}
