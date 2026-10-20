"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { TripForm } from "@/components/trip-form";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TripInput } from "@/lib/types";

export default function NewTripPage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();

  const create = useMutation({
    mutationFn: (data: TripInput) => api.createTrip(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      router.push("/trips");
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("trips.add")} backHref="/trips" backLabel={t("common.back")} />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <TripForm submitting={create.isPending} onSubmit={(data) => create.mutate(data)} />
      </div>
    </div>
  );
}
