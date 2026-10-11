"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

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
      router.push("/transports");
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <Link
        href="/transports"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("common.back")}
      </Link>
      <h1 className="font-display text-3xl font-semibold tracking-tight">
        {t("transports.add")}
      </h1>
      <TransportForm submitting={create.isPending} onSubmit={(data) => create.mutate(data)} />
    </div>
  );
}