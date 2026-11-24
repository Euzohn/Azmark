"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MoreHorizontal, MapPin, MapPinOff, Pencil, Trash2 } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AttachmentPanel } from "@/components/attachment-panel";
import { HotelForm } from "@/components/hotel-form";
import { HotelSummary } from "@/components/hotel-summary";
import { LinkedExpenses } from "@/components/linked-expenses";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { hotelsReturnHref } from "@/lib/record-navigation";
import type { HotelGeocodeCandidate, HotelInput } from "@/lib/types";

function HotelDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const backHref = hotelsReturnHref(searchParams.get("from"));
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  const [geocodedAddress, setGeocodedAddress] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<HotelGeocodeCandidate[] | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["hotel", id],
    queryFn: () => api.getHotel(id),
    enabled: Boolean(id),
  });

  const refresh = async () => {
    await Promise.all(
      ["hotels", "hotel", "trips", "trip", "dashboard", "map-routes"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      ),
    );
  };

  const update = useMutation({
    mutationFn: (input: HotelInput) => api.updateHotel(id, input),
    onSuccess: async (hotel) => {
      queryClient.setQueryData(["hotel", id], hotel);
      setDirty(false);
      setEditing(false);
      setSaved(true);
      await refresh();
    },
  });

  const clearLocation = useMutation({
    // Explicit nulls (not omitted fields) tell the API to drop the pin.
    mutationFn: () => api.updateHotel(id, { lat: null, lon: null }),
    onSuccess: async (hotel) => {
      queryClient.setQueryData(["hotel", id], hotel);
      setGeocodedAddress(null);
      await refresh();
    },
  });

  const geocode = useMutation({
    mutationFn: () => api.geocodeHotel(id),
    onSuccess: (result) => {
      // Lookup only: nothing is pinned until the user picks a candidate.
      setCandidates(result.candidates);
    },
  });

  const applyLocation = useMutation({
    mutationFn: (input: HotelInput) => api.updateHotel(id, input),
    onSuccess: async (hotel) => {
      queryClient.setQueryData(["hotel", id], hotel);
      setCandidates(null);
      clearLocation.reset();
      await refresh();
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteHotel(id),
    onSuccess: async () => {
      await refresh();
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

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={t(editing ? "hotels.edit" : "hotels.detail")}
        backHref={backHref}
        backLabel={t("common.back")}
        actions={
          editing ? undefined : (
            <>
              <Button
                variant="outline"
                onClick={() => {
                  setGeocodedAddress(null);
                  clearLocation.reset();
                  applyLocation.reset();
                  geocode.mutate();
                }}
                disabled={geocode.isPending}
              >
                <MapPin className="h-4 w-4" />
                {t(geocode.isPending ? "hotels.locating" : "hotels.locate")}
              </Button>
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
      {applyLocation.isSuccess && !editing ? (
        <p role="status" className="text-sm text-success">
          {geocodedAddress
            ? t("hotels.locatedAt", { address: geocodedAddress })
            : t("hotels.located")}
        </p>
      ) : null}
      {geocode.isError && !editing ? (
        <p role="alert" className="text-sm text-danger">
          {t(
            geocode.error instanceof ApiError && geocode.error.status === 503
              ? "hotels.locateUnavailable"
              : "hotels.locateFailed",
          )}
        </p>
      ) : null}
      {clearLocation.isSuccess && !editing ? (
        <p role="status" className="text-sm text-success">
          {t("hotels.locationCleared")}
        </p>
      ) : null}
      {clearLocation.isError && !editing ? (
        <p role="alert" className="text-sm text-danger">
          {t("common.error")}
        </p>
      ) : null}
      {editing ? (
        <>
          {update.isError ? (
            <p role="alert" className="text-sm text-danger">
              {t("common.error")}
            </p>
          ) : null}
          <HotelForm
            initial={data}
            submitting={update.isPending}
            onDirtyChange={setDirty}
            onCancel={cancel}
            onSubmit={(input) => update.mutate(input)}
          />
        </>
      ) : (
        <>
          <HotelSummary hotel={data} />
          <AttachmentPanel resourceType="hotel" resourceId={id} />
          <LinkedExpenses sourceType="hotel" sourceId={id} />
        </>
      )}
      <Dialog
        open={moreOpen}
        onClose={() => setMoreOpen(false)}
        title={t("common.actions")}
        variant="responsive"
      >
        {data.lat != null || data.lon != null ? (
          <Button
            variant="ghost"
            className="w-full justify-start"
            disabled={clearLocation.isPending}
            onClick={() => {
              setMoreOpen(false);
              clearLocation.mutate();
            }}
          >
            <MapPinOff className="h-4 w-4" />
            {t("hotels.clearLocation")}
          </Button>
        ) : null}
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
        <p className="text-sm text-muted-foreground">{t("hotels.deleteConfirm")}</p>
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
          <Button
            variant="danger"
            disabled={remove.isPending}
            onClick={() => remove.mutate()}
          >
            {t(remove.isPending ? "common.loading" : "common.delete")}
          </Button>
        </div>
      </Dialog>
      <Dialog
        open={candidates !== null}
        onClose={() => {
          if (!applyLocation.isPending) setCandidates(null);
        }}
        title={t("hotels.chooseLocation")}
        variant="responsive"
      >
        <p className="text-sm text-muted-foreground">{t("hotels.chooseLocationHint")}</p>
        <div className="mt-4 flex flex-col gap-2">
          {(candidates ?? []).map((candidate, index) => (
            <button
              key={`${candidate.lat}-${candidate.lon}-${index}`}
              type="button"
              disabled={applyLocation.isPending}
              onClick={() => {
                // Overwriting an existing (possibly hand-entered) pin needs
                // an explicit second confirmation.
                if (
                  (data.lat != null || data.lon != null) &&
                  !window.confirm(t("hotels.overwriteLocationConfirm"))
                ) {
                  return;
                }
                setGeocodedAddress(candidate.display_name);
                applyLocation.mutate({ lat: candidate.lat, lon: candidate.lon });
              }}
              className="flex flex-col gap-1 rounded-lg border border-border bg-background px-3 py-2.5 text-left transition-colors hover:bg-accent disabled:opacity-60"
            >
              <span className="text-sm font-medium">
                {candidate.display_name ||
                  `${candidate.lat.toFixed(5)}, ${candidate.lon.toFixed(5)}`}
              </span>
              <span className="text-xs tabular-nums text-muted-foreground">
                {candidate.lat.toFixed(5)}, {candidate.lon.toFixed(5)}
                {candidate.provider ? ` · ${candidate.provider}` : ""}
              </span>
            </button>
          ))}
        </div>
        {applyLocation.isError ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {t("common.error")}
          </p>
        ) : null}
        <div className="mt-6 flex justify-end">
          <Button
            variant="outline"
            disabled={applyLocation.isPending}
            onClick={() => setCandidates(null)}
          >
            {t("common.cancel")}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Skeleton className="h-12 w-64" />
      <Skeleton className="h-64 w-full rounded-xl" />
      <Skeleton className="h-48 w-full rounded-xl" />
    </div>
  );
}

export default function HotelDetailPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <HotelDetail />
    </Suspense>
  );
}
