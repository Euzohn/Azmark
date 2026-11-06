"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { NoteForm } from "@/components/note-form";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { NoteInput } from "@/lib/types";

function localReturnHref(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;
  return value;
}

function NewNoteContent() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const initialTripId = searchParams.get("trip_id");
  const returnTo = localReturnHref(searchParams.get("return_to")) ?? "/notes";

  const create = useMutation({
    mutationFn: (data: NoteInput) => api.createNote(data),
    onSuccess: () => {
      for (const key of ["notes", "trips", "trip"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      router.push(returnTo);
    },
    onError: () => setError(t("common.error")),
  });

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={t("notes.add")}
        backHref={initialTripId ? returnTo : "/notes"}
        backLabel={t("common.back")}
      />
      <div className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <NoteForm
          initialTripId={initialTripId}
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

export default function NewNotePage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto flex max-w-5xl flex-col gap-6">
          <Skeleton className="h-12 w-64" />
          <Skeleton className="h-80 w-full rounded-xl" />
        </div>
      }
    >
      <NewNoteContent />
    </Suspense>
  );
}
