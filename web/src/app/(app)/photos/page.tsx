"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Image as ImageIcon, Plus, Search, Sparkles, Upload } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { PhotoImage } from "@/components/photo-image";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Fab } from "@/components/ui/fab";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { saveScroll, takeScroll } from "@/lib/scroll-memory";
import { useI18n } from "@/lib/i18n";
import { usePageTitle } from "@/lib/page-title";
import type { PhotoFilters, PhotoSuggestion, PhotoTripCandidate } from "@/lib/types";
import { cn } from "@/lib/utils";

function formatDay(value: string | null, locale: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" });
}

/** Review deterministic trip suggestions, then file the checked photos.
 * Nothing is written until the user presses the confirm button (spec #33). */
function OrganizeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["photo-suggestions"],
    queryFn: api.getPhotoSuggestions,
    enabled: open,
  });
  const [overrides, setOverrides] = useState<
    Record<string, { tripId?: string; included?: boolean }>
  >({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Defaults derive from the query data (strongest candidate, included);
  // user edits live in `overrides`, so no effect has to sync state.
  const choiceFor = (item: PhotoSuggestion) => {
    const override = overrides[item.photo.id] ?? {};
    return {
      tripId: override.tripId ?? item.candidates[0]?.trip_id ?? "",
      included: override.included ?? true,
    };
  };

  const close = () => {
    setOverrides({});
    setError(null);
    onClose();
  };

  const items = data?.items ?? [];
  const selected = items.filter((item) => {
    const choice = choiceFor(item);
    return choice.included && choice.tripId;
  });

  const apply = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.organizePhotos(
        selected.map((item) => ({
          photo_id: item.photo.id,
          trip_id: choiceFor(item).tripId,
        })),
      );
      await queryClient.invalidateQueries({ queryKey: ["photos"] });
      await queryClient.invalidateQueries({ queryKey: ["photo-suggestions"] });
      close();
    } catch {
      setError(t("photos.organizeFailed"));
    } finally {
      setSaving(false);
    }
  };

  const reasonLabel = (candidate: PhotoTripCandidate): string =>
    candidate.reasons
      .map((reason) =>
        reason === "time"
          ? t("photos.organizeReasonTime")
          : t("photos.organizeReasonGeo", { distance: candidate.distance_km ?? 0 }),
      )
      .join(" · ");

  return (
    <Dialog
      open={open}
      onClose={close}
      title={t("photos.organizeTitle")}
      variant="responsive"
      className="md:max-w-lg"
    >
      {isLoading ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-lg" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="py-6 text-center">
          <p className="text-sm font-medium">{t("photos.organizeEmpty")}</p>
          <p className="mt-1 text-xs text-muted-foreground">{t("photos.organizeEmptyHint")}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-muted-foreground">{t("photos.organizeHint")}</p>
          {items.map((item) => {
            const choice = choiceFor(item);
            const active = item.candidates.find((c) => c.trip_id === choice.tripId);
            return (
              <div key={item.photo.id} className="flex gap-3 rounded-lg border border-border p-3">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 shrink-0 accent-primary"
                  checked={choice.included}
                  aria-label={item.photo.filename}
                  onChange={(event) =>
                    setOverrides((prev) => ({
                      ...prev,
                      [item.photo.id]: { ...prev[item.photo.id], included: event.target.checked },
                    }))
                  }
                />
                <div className="h-14 w-14 shrink-0 overflow-hidden rounded-md border border-border bg-muted">
                  <PhotoImage
                    id={item.photo.id}
                    alt={item.photo.filename}
                    className="h-full w-full object-cover"
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{item.photo.filename}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDay(item.photo.captured_at, locale) || t("photos.noDate")}
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {item.candidates.map((candidate) => (
                      <button
                        key={candidate.trip_id}
                        type="button"
                        onClick={() =>
                          setOverrides((prev) => ({
                            ...prev,
                            [item.photo.id]: {
                              ...prev[item.photo.id],
                              tripId: candidate.trip_id,
                              included: true,
                            },
                          }))
                        }
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-xs transition-colors",
                          choice.tripId === candidate.trip_id
                            ? "border-primary bg-primary/10 font-medium text-primary"
                            : "border-border text-muted-foreground hover:bg-muted",
                        )}
                      >
                        {candidate.trip_name}
                      </button>
                    ))}
                  </div>
                  {active ? (
                    <p className="mt-1 text-[11px] text-muted-foreground">{reasonLabel(active)}</p>
                  ) : null}
                </div>
              </div>
            );
          })}
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}
          <Button
            className="w-full"
            disabled={saving || selected.length === 0}
            onClick={() => void apply()}
          >
            <Sparkles className="h-4 w-4" />
            {t("photos.organizeApply", { count: selected.length })}
          </Button>
        </div>
      )}
    </Dialog>
  );
}

function PhotosContent() {
  const { t, locale } = useI18n();
  usePageTitle(t("nav.photos"));
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const tripId = searchParams.get("trip_id") ?? undefined;
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");
  const [sort, setSort] = useState<PhotoFilters["sort"]>("newest");
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [organizeOpen, setOrganizeOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["photos", { search, sort, trip_id: tripId }],
    queryFn: () =>
      api.listPhotos({
        search: search || undefined,
        sort,
        trip_id: tripId,
        page_size: 100,
      }),
  });

  // Keep the search term in the URL so it survives the trip to a detail page.
  useEffect(() => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (tripId) params.set("trip_id", tripId);
    const query = params.toString();
    window.history.replaceState(null, "", `/photos${query ? `?${query}` : ""}`);
  }, [search, tripId]);

  const scrollRestored = useRef(false);
  useEffect(() => {
    if (scrollRestored.current || !data) return;
    scrollRestored.current = true;
    const y = takeScroll(window.location.pathname + window.location.search);
    if (y === null) return;
    window.scrollTo(0, y);
    requestAnimationFrame(() => window.scrollTo(0, y));
  }, [data]);

  // Map the server's rejection to a specific, translated reason instead of
  // one catch-all message (HEIC hints and size limits were being swallowed).
  const uploadReason = (error: unknown): string => {
    if (error instanceof ApiError) {
      if (error.status === 413) return t("photos.uploadTooLarge");
      if (error.status === 415) return t("photos.uploadUnsupported");
      if (error.status === 502) return t("photos.uploadStorageDown");
    }
    return t("photos.uploadFailed");
  };

  const handleFiles = async (files: File[]) => {
    if (files.length === 0) return;
    setUploadError(null);
    setProgress({ done: 0, total: files.length });
    let failed = 0;
    let reason: string | null = null;
    // Sequential uploads keep memory flat and let each file report its own
    // failure without cancelling the rest of the batch.
    for (const file of files) {
      try {
        await api.uploadPhoto(file, { trip_id: tripId });
      } catch (error) {
        failed += 1;
        reason ??= uploadReason(error);
      }
      setProgress((prev) => (prev ? { ...prev, done: prev.done + 1 } : prev));
    }
    setProgress(null);
    if (failed > 0) {
      const detail = reason ?? t("photos.uploadFailed");
      setUploadError(
        failed === files.length
          ? detail
          : `${t("photos.uploadPartial", { count: failed })} · ${detail}`,
      );
    }
    await queryClient.invalidateQueries({ queryKey: ["photos"] });
  };

  const uploading = progress !== null;
  const fromParams = new URLSearchParams();
  if (search) fromParams.set("search", search);
  if (tripId) fromParams.set("trip_id", tripId);
  const fromHref = fromParams.toString() ? `/photos?${fromParams.toString()}` : "/photos";

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("photos.title")}
        subtitle={data ? t("records.total", { count: data.total }) : t("photos.subtitle")}
        actions={
          <>
            <Button
              variant="outline"
              size="icon"
              className="md:hidden"
              aria-label={t("photos.organize")}
              disabled={uploading}
              onClick={() => setOrganizeOpen(true)}
            >
              <Sparkles className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              className="hidden md:inline-flex"
              disabled={uploading}
              onClick={() => setOrganizeOpen(true)}
            >
              <Sparkles className="h-4 w-4" />
              {t("photos.organize")}
            </Button>
            <Button
              className="hidden md:inline-flex"
              disabled={uploading}
              onClick={() => inputRef.current?.click()}
            >
              <Upload className="h-4 w-4" />
              {uploading ? t("photos.uploading", progress ?? undefined) : t("photos.upload")}
            </Button>
          </>
        }
      />

      <input
        ref={inputRef}
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={(event) => {
          // Copy the FileList before resetting the input: clearing `value`
          // empties the live FileList in some browsers.
          const files = event.target.files ? Array.from(event.target.files) : [];
          // Reset so selecting the same file again still triggers onChange.
          event.target.value = "";
          void handleFiles(files);
        }}
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-10"
            placeholder={t("photos.searchPlaceholder")}
            aria-label={t("common.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          aria-label={t("photos.sort.newest")}
          value={sort}
          onChange={(e) => setSort(e.target.value as PhotoFilters["sort"])}
          className="sm:w-52"
        >
          <option value="newest">{t("photos.sort.newest")}</option>
          <option value="oldest">{t("photos.sort.oldest")}</option>
          <option value="uploaded">{t("photos.sort.uploaded")}</option>
        </Select>
      </div>

      {uploadError ? (
        <p role="alert" className="text-sm text-danger">
          {uploadError}
        </p>
      ) : null}
      {uploading ? (
        <p role="status" className="text-sm text-muted-foreground">
          {t("photos.uploading", progress ?? undefined)}
        </p>
      ) : null}

      {isError ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-4 rounded-xl border border-danger/30 bg-card p-5"
        >
          <p className="text-sm text-danger">{t("common.error")}</p>
          <Button variant="outline" onClick={() => void refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="aspect-square w-full rounded-xl" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={ImageIcon}
          title={t("photos.empty")}
          hint={t("photos.emptyHint")}
          action={
            <Button variant="outline" disabled={uploading} onClick={() => inputRef.current?.click()}>
              <Plus className="h-4 w-4" />
              {t("photos.upload")}
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {data.items.map((photo) => {
            const day = formatDay(photo.captured_at, locale);
            return (
              <Link
                key={photo.id}
                href={`/photos/${photo.id}?from=${encodeURIComponent(fromHref)}`}
                onClick={() => saveScroll(window.location.pathname + window.location.search)}
                className="group flex min-w-0 flex-col gap-2 focus-visible:outline-none"
              >
                <div className="relative aspect-square overflow-hidden rounded-xl border border-border bg-muted">
                  <PhotoImage
                    id={photo.id}
                    alt={photo.filename}
                    className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                  />
                  {day ? (
                    <span className="absolute bottom-2 left-2 rounded bg-black/55 px-2 py-0.5 text-[11px] font-medium text-white">
                      {day}
                    </span>
                  ) : null}
                </div>
                <span className="truncate text-xs text-muted-foreground">{photo.filename}</span>
              </Link>
            );
          })}
        </div>
      )}

      <OrganizeDialog open={organizeOpen} onClose={() => setOrganizeOpen(false)} />

      <Fab
        label={t("photos.upload")}
        onClick={() => {
          if (!uploading) inputRef.current?.click();
        }}
      >
        <Upload className="h-6 w-6" />
      </Fab>
    </div>
  );
}

export default function PhotosPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-5">
          <Skeleton className="h-10 w-56" />
          <Skeleton className="h-10 w-full" />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="aspect-square w-full rounded-xl" />
            ))}
          </div>
        </div>
      }
    >
      <PhotosContent />
    </Suspense>
  );
}
