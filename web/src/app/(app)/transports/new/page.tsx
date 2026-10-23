"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { DuplicateDialog, type ExistingRecord } from "@/components/duplicate-dialog";
import { PageHeader } from "@/components/page-header";
import { TransportForm } from "@/components/transport-form";
import { ApiError, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { OtherTransportInput } from "@/lib/types";

export default function NewTransportPage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<OtherTransportInput | null>(null);
  const [duplicate, setDuplicate] = useState<ExistingRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: ({ data, force }: { data: OtherTransportInput; force: boolean }) =>
      api.createOtherTransport(data, force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transports"] });
      router.push("/records?type=other");
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

  const submit = (data: OtherTransportInput, force = false) => {
    setError(null);
    setPending(data);
    create.mutate({ data, force });
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("transports.add")} backHref="/records?type=other" backLabel={t("common.back")} />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <TransportForm submitting={create.isPending} onSubmit={(data) => submit(data)} />
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <DuplicateDialog
        open={duplicate !== null}
        record={duplicate}
        recordType="other"
        submitting={create.isPending}
        onOpenExisting={() => {
          if (duplicate) router.push(`/transports/${duplicate.id}`);
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