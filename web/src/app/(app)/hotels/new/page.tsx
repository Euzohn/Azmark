"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { DuplicateDialog, type ExistingRecord } from "@/components/duplicate-dialog";
import { HotelForm } from "@/components/hotel-form";
import { PageHeader } from "@/components/page-header";
import { ApiError, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { HotelInput } from "@/lib/types";

export default function NewHotelPage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<HotelInput | null>(null);
  const [duplicate, setDuplicate] = useState<ExistingRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: ({ data, force }: { data: HotelInput; force: boolean }) =>
      api.createHotel(data, force),
    onSuccess: () => {
      for (const key of ["hotels", "trips", "trip", "dashboard"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      router.push("/hotels");
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

  const submit = (data: HotelInput, force = false) => {
    setError(null);
    setPending(data);
    create.mutate({ data, force });
  };

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={t("hotels.add")}
        backHref="/hotels"
        backLabel={t("common.back")}
      />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <HotelForm submitting={create.isPending} onSubmit={(data) => submit(data)} />
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <DuplicateDialog
        open={duplicate !== null}
        record={duplicate}
        recordType="hotel"
        submitting={create.isPending}
        onOpenExisting={() => {
          if (duplicate) router.push(`/hotels/${duplicate.id}`);
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
