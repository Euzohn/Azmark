"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Paperclip, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type ResourceType = "flight" | "train" | "transport";

interface AttachmentPanelProps {
  resourceType: ResourceType;
  resourceId: string;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function AttachmentPanel({ resourceType, resourceId }: AttachmentPanelProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["attachments", resourceType, resourceId],
    queryFn: () => api.listAttachments(resourceType, resourceId),
    enabled: Boolean(resourceId),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ["attachments", resourceType, resourceId],
    });

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadAttachment(resourceType, resourceId, file),
    onMutate: () => setError(null),
    onSuccess: () => {
      setError(null);
      void invalidate();
    },
    onError: () => setError(t("attachments.uploadFailed")),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteAttachment(id),
    onMutate: () => setError(null),
    onSuccess: () => {
      setError(null);
      void invalidate();
    },
    onError: () => setError(t("attachments.deleteFailed")),
  });

  const download = async (id: string, filename: string) => {
    setError(null);
    setDownloading(id);
    try {
      saveBlob(await api.downloadAttachment(id), filename);
    } catch {
      setError(t("attachments.downloadFailed"));
    } finally {
      setDownloading(null);
    }
  };

  const items = data?.items ?? [];
  const busy = upload.isPending || remove.isPending;

  return (
    <Card className="animate-fade-in-up">
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <CardTitle>{t("attachments.title")}</CardTitle>
          <p className="text-sm text-muted-foreground">{t("attachments.hint")}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={upload.isPending}
          onClick={() => inputRef.current?.click()}
        >
          <Upload className="h-4 w-4" />
          {upload.isPending ? t("attachments.uploading") : t("attachments.add")}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*,application/pdf"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Reset so selecting the same file again still triggers onChange.
            event.target.value = "";
            if (file) upload.mutate(file);
          }}
        />
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-4 py-6 text-center">
            <p className="text-sm font-medium">{t("attachments.empty")}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("attachments.emptyHint")}
            </p>
          </div>
        ) : (
          items.map((attachment) => (
            <div
              key={attachment.id}
              className="flex items-center gap-3 rounded-xl border border-border px-3 py-2"
            >
              <Paperclip className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{attachment.filename}</p>
                <p className="text-xs text-muted-foreground">
                  {formatSize(attachment.size)}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                disabled={downloading === attachment.id}
                onClick={() => void download(attachment.id, attachment.filename)}
                title={t("attachments.download")}
                aria-label={t("attachments.download")}
              >
                <Download className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                disabled={busy}
                onClick={() => {
                  if (window.confirm(t("attachments.deleteConfirm"))) {
                    remove.mutate(attachment.id);
                  }
                }}
                title={t("attachments.delete")}
                aria-label={t("attachments.delete")}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
