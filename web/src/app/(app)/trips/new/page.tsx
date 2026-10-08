"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

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
      <Link
        href="/trips"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("common.back")}
      </Link>
      <h1 className="text-xl font-semibold tracking-tight">{t("trips.add")}</h1>
      <TripForm submitting={create.isPending} onSubmit={(data) => create.mutate(data)} />
    </div>
  );
}
