"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { DuplicateDialog, type ExistingRecord } from "@/components/duplicate-dialog";
import { PageHeader } from "@/components/page-header";
import { TrainForm } from "@/components/train-form";
import { ApiError, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TrainInput } from "@/lib/types";

export default function NewTrainPage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<TrainInput | null>(null);
  const [duplicate, setDuplicate] = useState<ExistingRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: ({ data, force }: { data: TrainInput; force: boolean }) =>
      api.createTrain(data, force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trains"] });
      router.push("/records?type=train");
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        const detail = err.detail as { existing_record?: ExistingRecord } | undefined;
        if (detail?.existing_record) {
          setDuplicate(detail.existing_record);
          return;
        }
      }
      setError(t("records.createFailed"));
    },
  });

  const submit = (data: TrainInput, force = false) => {
    setError(null);
    setPending(data);
    create.mutate({ data, force });
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("trains.add")} backHref="/records?type=train" backLabel={t("common.back")} />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <TrainForm submitting={create.isPending} onSubmit={(data) => submit(data)} />
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <DuplicateDialog
        open={duplicate !== null}
        record={duplicate}
        recordType="train"
        submitting={create.isPending}
        onOpenExisting={() => {
          if (duplicate) router.push(`/trains/${duplicate.id}`);
        }}
        onKeepNew={() => {
          if (!pending) return;
          setDuplicate(null);
          submit(pending, true);
        }}
        onCancel={() => setDuplicate(null)}
      />
    </div>
  );
}