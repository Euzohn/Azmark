"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { FlightForm } from "@/components/flight-form";
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
      router.push("/flights");
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <Link
        href="/flights"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("common.back")}
      </Link>
      <h1 className="text-xl font-semibold">{t("flights.add")}</h1>
      <FlightForm submitting={create.isPending} onSubmit={(data) => create.mutate(data)} />
    </div>
  );
}
