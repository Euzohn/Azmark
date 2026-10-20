"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";

import { AttachmentPanel } from "@/components/attachment-panel";
import { PageHeader } from "@/components/page-header";
import { TransportForm } from "@/components/transport-form";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { OtherTransportInput } from "@/lib/types";

export default function TransportDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data, isLoading } = useQuery({
    queryKey: ["transport", id],
    queryFn: () => api.getOtherTransport(id),
    enabled: Boolean(id),
  });

  const update = useMutation({
    mutationFn: (input: OtherTransportInput) => api.updateOtherTransport(id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transports"] });
      queryClient.invalidateQueries({ queryKey: ["transport", id] });
      router.push("/records?type=other");
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteOtherTransport(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transports"] });
      router.push("/records?type=other");
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
      <PageHeader
        title={t("transports.edit")}
        backHref="/records?type=other"
        backLabel={t("common.back")}
        actions={
          <Button
            variant="danger"
            size="sm"
            onClick={() => {
              if (window.confirm(t("transports.deleteConfirm"))) {
                remove.mutate();
              }
            }}
          >
            <Trash2 className="h-4 w-4" />
            {t("common.delete")}
          </Button>
        }
      />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <TransportForm
          initial={data}
          submitting={update.isPending}
          onSubmit={(input) => update.mutate(input)}
        />
      </div>
      <AttachmentPanel resourceType="transport" resourceId={id} />
    </div>
  );
}