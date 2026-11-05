"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { PlaceForm } from "@/components/place-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DateTimeLocalInput } from "@/components/ui/date-input";
import { Dialog } from "@/components/ui/dialog";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { fromZonedInput } from "@/lib/datetime";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Place, PlaceInput, TripList } from "@/lib/types";

function PlaceDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [saved, setSaved] = useState(false);

  const [tripId, setTripId] = useState("");
  const [visitStart, setVisitStart] = useState("");
  const [visitEnd, setVisitEnd] = useState("");
  const [tripMessage, setTripMessage] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["place", id],
    queryFn: () => api.getPlace(id),
    enabled: Boolean(id),
  });

  const { data: trips } = useQuery<TripList>({
    queryKey: ["trips", { page_size: 100 }],
    queryFn: () => api.listTrips({ page_size: 100 }),
  });

  const update = useMutation({
    mutationFn: (input: PlaceInput) => api.updatePlace(id, input),
    onSuccess: async (place) => {
      queryClient.setQueryData(["place", id], place);
      setDirty(false);
      setEditing(false);
      setSaved(true);
      await Promise.all(
        ["places", "place", "trips", "trip", "dashboard"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deletePlace(id),
    onSuccess: async () => {
      await Promise.all(
        ["places", "place", "trips", "trip", "dashboard"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
      router.replace("/places");
    },
  });

  const addToTrip = useMutation({
    mutationFn: () =>
      api.addTripItem(tripId, {
        item_type: "place",
        item_id: id,
        start_at: fromZonedInput(visitStart),
        end_at: fromZonedInput(visitEnd),
      }),
    onSuccess: async () => {
      setTripMessage(t("places.addedToTrip"));
      setVisitStart("");
      setVisitEnd("");
      await Promise.all(
        ["trip", "trips", "dashboard"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setTripMessage(t("places.alreadyInTrip"));
      } else {
        setTripMessage(t("common.error"));
      }
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
        title={t(editing ? "places.edit" : "places.detail")}
        backHref="/places"
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
          <PlaceForm
            initial={data}
            submitting={update.isPending}
            onDirtyChange={setDirty}
            onCancel={cancel}
            onSubmit={(input) => update.mutate(input)}
          />
        </>
      ) : (
        <>
          <PlaceSummary place={data} />

          <Card>
            <CardContent className="flex flex-col gap-3 p-5">
              <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                {t("places.addToTrip")}
              </h2>
              <p className="text-xs text-muted-foreground">{t("places.addToTripHint")}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Select value={tripId} onChange={(e) => setTripId(e.target.value)}>
                  <option value="">{t("places.selectTrip")}</option>
                  {trips?.items.map((trip) => (
                    <option key={trip.id} value={trip.id}>
                      {trip.name}
                    </option>
                  ))}
                </Select>
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">{t("places.visitStart")}</span>
                    <DateTimeLocalInput
                      value={visitStart}
                      onChange={(e) => setVisitStart(e.target.value)}
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">{t("places.visitEnd")}</span>
                    <DateTimeLocalInput
                      value={visitEnd}
                      onChange={(e) => setVisitEnd(e.target.value)}
                    />
                  </label>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Button
                  disabled={!tripId || addToTrip.isPending}
                  onClick={() => {
                    setTripMessage(null);
                    addToTrip.mutate();
                  }}
                >
                  {addToTrip.isPending ? t("common.loading") : t("places.addToTrip")}
                </Button>
                {tripMessage ? (
                  <span role="status" className="text-sm text-muted-foreground">
                    {tripMessage}
                  </span>
                ) : null}
              </div>
            </CardContent>
          </Card>
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
        <p className="text-sm text-muted-foreground">{t("places.deleteConfirm")}</p>
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

function PlaceSummary({ place }: { place: Place }) {
  const { t } = useI18n();
  const location = [place.country, place.region, place.city, place.district]
    .filter(Boolean)
    .join(" · ");
  const coords =
    place.lat != null && place.lon != null ? `${place.lat}, ${place.lon}` : null;
  const fields: [TranslationKey, string | null][] = [
    ["places.type", t(`places.type.${place.type}`)],
    ["places.localizedName", place.localized_name],
    ["places.location", location || null],
    ["places.lat", coords],
    ["places.timezone", place.timezone],
  ];

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 md:px-7">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <MapPin className="h-4 w-4" strokeWidth={1.75} />
          </span>
          <div className="min-w-0">
            <div className="font-display text-lg font-semibold tracking-tight">{place.name}</div>
            {place.localized_name ? (
              <div className="mt-0.5 text-xs text-muted-foreground">{place.localized_name}</div>
            ) : null}
          </div>
        </div>
        <Badge variant="neutral">{t(`places.type.${place.type}`)}</Badge>
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

export default function PlaceDetailPage() {
  return <PlaceDetail />;
}
