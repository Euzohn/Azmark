"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { TransportForm } from "@/components/transport-form";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { OtherTransportInput } from "@/lib/types";

export default function NewTransportPage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();

  const create = useMutation({
    mutationFn: (data: OtherTransportInput) => api.createOtherTransport(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transports"] });
      router.push("/records?type=other");
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("transports.add")} backHref="/records?type=other" backLabel={t("common.back")} />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <TransportForm submitting={create.isPending} onSubmit={(data) => create.mutate(data)} />
      </div>
    </div>
  );
}