"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { NoteForm } from "@/components/note-form";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { NoteInput } from "@/lib/types";

export default function NewNotePage() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (data: NoteInput) => api.createNote(data),
    onSuccess: () => {
      for (const key of ["notes", "trips", "trip"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      router.push("/notes");
    },
    onError: () => setError(t("common.error")),
  });

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t("notes.add")} backHref="/notes" backLabel={t("common.back")} />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <NoteForm
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
