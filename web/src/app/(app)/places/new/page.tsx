"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { PlaceForm } from "@/components/place-form";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { PlaceInput } from "@/lib/types";

export default function NewPlacePage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (data: PlaceInput) => api.createPlace(data),
    onSuccess: () => {
      for (const key of ["places", "trips", "trip", "dashboard"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      router.push("/places");
    },
    onError: () => setError(t("common.error")),
  });

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={t("places.add")}
        backHref="/places"
        backLabel={t("common.back")}
      />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <PlaceForm
          submitting={create.isPending}
          onSubmit={(data) => {
            setError(null);
            create.mutate(data);
          }}
        />
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
    </div>
  );
}
