"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { PhotoForm } from "@/components/photo-form";
import { PhotoImage } from "@/components/photo-image";
import { TripLinkCard } from "@/components/trip-link-card";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api, photoImageUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { PhotoInput } from "@/lib/types";

function photoReturnHref(from: string | null): string {
  // Photos are opened from the album or from a trip's photo section.
  if (from && (from.startsWith("/photos") || from.startsWith("/trips"))) return from;
  return "/photos";
}

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

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function formatCoordinates(latitude: number | null, longitude: number | null): string | null {
  if (latitude === null || longitude === null) return null;
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}

function PhotoDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const backHref = photoReturnHref(searchParams.get("from"));
  const queryClient = useQueryClient();
  const { t, locale } = useI18n();
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [saved, setSaved] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["photo", id],
    queryFn: () => api.getPhoto(id),
    enabled: Boolean(id),
  });

  const update = useMutation({
    mutationFn: (input: PhotoInput) => api.updatePhoto(id, input),
    onSuccess: async (photo) => {
      queryClient.setQueryData(["photo", id], photo);
      setDirty(false);
      setEditing(false);
      setSaved(true);
      await Promise.all(
        ["photos", "photo", "trips", "trip"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deletePhoto(id),
    onSuccess: async () => {
      await Promise.all(
        ["photos", "photo", "trips", "trip"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
      router.replace(backHref);
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

  const coordinates = formatCoordinates(data.latitude, data.longitude);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <PageHeader
        title={t(editing ? "photos.edit" : "photos.detail")}
        backHref={backHref}
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
          <PhotoForm
            initial={data}
            submitting={update.isPending}
            onDirtyChange={setDirty}
            onCancel={cancel}
            onSubmit={(input) => update.mutate(input)}
          />
        </>
      ) : (
        <>
          <section className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="flex min-h-[16rem] items-center justify-center bg-black/5 p-2 md:p-4">
              <PhotoImage
                id={data.id}
                alt={data.filename}
                variant="full"
                eager
                className="max-h-[70vh] w-full rounded-lg object-contain"
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4 md:px-7">
              <div className="min-w-0">
                <div className="truncate font-display text-lg font-semibold tracking-tight">
                  {data.filename}
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {t("photos.fileInfo", { type: data.mime_type, size: formatSize(data.size) })}
                </div>
              </div>
              <a
                href={photoImageUrl(data.id, "full")}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
              >
                <ExternalLink className="h-4 w-4" />
                {t("photos.openOriginal")}
              </a>
            </div>
          </section>

          <dl className="grid gap-4 rounded-xl border border-border bg-card p-5 sm:grid-cols-3 md:p-7">
            <div className="min-w-0">
              <dt className="text-xs font-medium text-muted-foreground">
                {t("photos.capturedAt")}
              </dt>
              <dd className="mt-1 text-sm">
                {data.captured_at
                  ? formatDateTime(data.captured_at, locale)
                  : t("photos.noDate")}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs font-medium text-muted-foreground">
                {t("photos.location")}
              </dt>
              <dd className="mt-1 text-sm">{coordinates ?? t("photos.noLocation")}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs font-medium text-muted-foreground">
                {t("photos.uploadedAt")}
              </dt>
              <dd className="mt-1 text-sm">{formatDateTime(data.created_at, locale)}</dd>
            </div>
          </dl>

          {data.trip_id ? (
            <TripLinkCard tripId={data.trip_id} label={t("photos.trip")} />
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
        <p className="text-sm text-muted-foreground">{t("photos.deleteConfirm")}</p>
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

function DetailSkeleton() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <Skeleton className="h-12 w-64" />
      <Skeleton className="h-96 w-full rounded-xl" />
      <Skeleton className="h-24 w-full rounded-xl" />
    </div>
  );
}

export default function PhotoDetailPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <PhotoDetail />
    </Suspense>
  );
}
