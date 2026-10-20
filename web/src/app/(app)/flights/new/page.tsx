"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { FlightForm } from "@/components/flight-form";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { FlightInput } from "@/lib/types";

export default function NewFlightPage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();

  const create = useMutation({
    mutationFn: (data: FlightInput) => api.createFlight(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["flights"] });
      router.push("/records?type=flight");
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("flights.add")} backHref="/records?type=flight" backLabel={t("common.back")} />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <FlightForm submitting={create.isPending} onSubmit={(data) => create.mutate(data)} />
      </div>
    </div>
  );
}
