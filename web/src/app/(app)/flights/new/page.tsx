"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { DuplicateDialog, type ExistingRecord } from "@/components/duplicate-dialog";
import { FlightForm } from "@/components/flight-form";
import { PageHeader } from "@/components/page-header";
import { ApiError, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { FlightInput } from "@/lib/types";

export default function NewFlightPage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<FlightInput | null>(null);
  const [duplicate, setDuplicate] = useState<ExistingRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: ({ data, force }: { data: FlightInput; force: boolean }) =>
      api.createFlight(data, force),
    onSuccess: () => {
      for (const key of ["flights", "records", "timeline", "dashboard", "statistics", "stats", "map-routes", "trips", "trip"]) void queryClient.invalidateQueries({ queryKey: [key] });
      router.push("/records?type=flight");
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

  const submit = (data: FlightInput, force = false) => {
    setError(null);
    setPending(data);
    create.mutate({ data, force });
  };

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t("flights.add")} backHref="/records?type=flight" backLabel={t("common.back")} />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <FlightForm submitting={create.isPending} onSubmit={(data) => submit(data)} />
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <DuplicateDialog
        open={duplicate !== null}
        record={duplicate}
        recordType="flight"
        submitting={create.isPending}
        onOpenExisting={() => {
          if (duplicate) router.push(`/flights/${duplicate.id}`);
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
