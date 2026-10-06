"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { FlightForm } from "@/components/flight-form";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { FlightInput } from "@/lib/types";

export default function FlightDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data, isLoading } = useQuery({
    queryKey: ["flight", id],
    queryFn: () => api.getFlight(id),
    enabled: Boolean(id),
  });

  const update = useMutation({
    mutationFn: (input: FlightInput) => api.updateFlight(id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["flights"] });
      queryClient.invalidateQueries({ queryKey: ["flight", id] });
      router.push("/flights");
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteFlight(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["flights"] });
      router.push("/flights");
    },
  });

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;
  }
  if (!data) {
    return <p className="text-sm text-muted-foreground">{t("common.empty")}</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <Link
        href="/flights"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("common.back")}
      </Link>
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{t("flights.edit")}</h1>
        <Button
          variant="danger"
          size="sm"
          onClick={() => {
            if (window.confirm(t("flights.deleteConfirm"))) {
              remove.mutate();
            }
          }}
        >
          <Trash2 className="h-4 w-4" />
          {t("common.delete")}
        </Button>
      </div>
      <FlightForm
        initial={data}
        submitting={update.isPending}
        onSubmit={(input) => update.mutate(input)}
      />
    </div>
  );
}
