"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { TrainForm } from "@/components/train-form";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TrainInput } from "@/lib/types";

export default function NewTrainPage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();

  const create = useMutation({
    mutationFn: (data: TrainInput) => api.createTrain(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trains"] });
      router.push("/records?type=train");
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("trains.add")} backHref="/records?type=train" backLabel={t("common.back")} />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <TrainForm submitting={create.isPending} onSubmit={(data) => create.mutate(data)} />
      </div>
    </div>
  );
}
