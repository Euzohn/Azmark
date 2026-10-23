"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";

import { AttachmentPanel } from "@/components/attachment-panel";
import { AzmarkLoader } from "@/components/azmark-loader";
import { PageHeader } from "@/components/page-header";
import { TrainForm } from "@/components/train-form";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TrainInput } from "@/lib/types";

export default function TrainDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data, isLoading } = useQuery({
    queryKey: ["train", id],
    queryFn: () => api.getTrain(id),
    enabled: Boolean(id),
  });

  const update = useMutation({
    mutationFn: (input: TrainInput) => api.updateTrain(id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trains"] });
      queryClient.invalidateQueries({ queryKey: ["train", id] });
      router.push("/records?type=train");
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTrain(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trains"] });
      router.push("/records?type=train");
    },
  });

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <AzmarkLoader className="h-16 w-auto text-foreground" label={t("common.loading")} />
      </div>
    );
  }
  if (!data) {
    return <p className="text-sm text-muted-foreground">{t("common.empty")}</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("trains.edit")}
        backHref="/records?type=train"
        backLabel={t("common.back")}
        actions={
          <Button
            variant="danger"
            size="sm"
            onClick={() => {
              if (window.confirm(t("trains.deleteConfirm"))) {
                remove.mutate();
              }
            }}
          >
            <Trash2 className="h-4 w-4" />
            {t("common.delete")}
          </Button>
        }
      />
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 animate-fade-in-up" style={{ animationDelay: "50ms" }}>
          <TrainForm
            initial={data}
            submitting={update.isPending}
            onSubmit={(input) => update.mutate(input)}
          />
        </div>
        <div className="animate-fade-in-up xl:sticky xl:top-8" style={{ animationDelay: "100ms" }}>
          <AttachmentPanel resourceType="train" resourceId={id} />
        </div>
      </div>
    </div>
  );
}
