"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AttachmentPanel } from "@/components/attachment-panel";
import { PageHeader } from "@/components/page-header";
import { TrainForm } from "@/components/train-form";
import { TrainSummary } from "@/components/train-summary";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { recordsReturnHref } from "@/lib/record-navigation";
import type { TrainInput } from "@/lib/types";

function TrainDetail() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const backHref = recordsReturnHref(searchParams.get("from"), "/records?type=train");
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [saved, setSaved] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["train", id],
    queryFn: () => api.getTrain(id),
    enabled: Boolean(id),
  });
  const refresh = async () => {
    await Promise.all(
      ["trains", "records", "timeline", "dashboard", "statistics", "stats", "map-routes", "trips", "trip"].map(
        (key) => queryClient.invalidateQueries({ queryKey: [key] }),
      ),
    );
  };
  const update = useMutation({
    mutationFn: (input: TrainInput) => api.updateTrain(id, input),
    onSuccess: async (train) => {
      queryClient.setQueryData(["train", id], train);
      setDirty(false);
      setEditing(false);
      setSaved(true);
      await refresh();
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteTrain(id),
    onSuccess: async () => {
      await refresh();
      // A hard navigation also clears the deleted detail from the router cache.
      window.location.assign(backHref);
    },
  });
  const cancel = () => {
    if (dirty && !window.confirm(t("common.unsaved"))) return;
    setDirty(false);
    setEditing(false);
    update.reset();
  };

  if (isLoading) return <DetailSkeleton />;
  if (isError)
    return (
      <div role="alert" className="flex items-center gap-4">
        <p className="text-sm text-danger">{t("common.error")}</p>
        <Button variant="outline" onClick={() => void refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  if (!data) return <p>{t("common.empty")}</p>;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={t(editing ? "trains.edit" : "trains.detail")}
        backHref={backHref}
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
          <TrainForm
            initial={data}
            submitting={update.isPending}
            onDirtyChange={setDirty}
            onCancel={cancel}
            onSubmit={(input) => update.mutate(input)}
          />
        </>
      ) : (
        <>
          <TrainSummary train={data} />
          <AttachmentPanel resourceType="train" resourceId={id} />
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
        <p className="text-sm text-muted-foreground">{t("trains.deleteConfirm")}</p>
        {remove.isError ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {t("common.error")}
          </p>
        ) : null}
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="outline" disabled={remove.isPending} onClick={() => setDeleteOpen(false)}>
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
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Skeleton className="h-12 w-64" />
      <Skeleton className="h-64 w-full rounded-xl" />
      <Skeleton className="h-48 w-full rounded-xl" />
    </div>
  );
}

export default function TrainDetailPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <TrainDetail />
    </Suspense>
  );
}
