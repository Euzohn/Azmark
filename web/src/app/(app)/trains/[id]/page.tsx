"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

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
      router.push("/trains");
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTrain(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trains"] });
      router.push("/trains");
    },
  });

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;
  }
  if (!data) {
    return <p className="text-sm text-muted-foreground">{t("common.empty")}</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <Link
        href="/trains"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("common.back")}
      </Link>
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          {t("trains.edit")}
        </h1>
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
      </div>
      <TrainForm
        initial={data}
        submitting={update.isPending}
        onSubmit={(input) => update.mutate(input)}
      />
    </div>
  );
}
