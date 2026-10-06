"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plane, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Flight } from "@/lib/types";

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function FlightsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["flights", search],
    queryFn: () => api.listFlights({ search: search || undefined }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteFlight(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["flights"] }),
  });

  const handleDelete = (flight: Flight) => {
    if (window.confirm(t("flights.deleteConfirm"))) {
      remove.mutate(flight.id);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{t("flights.title")}</h1>
          {data ? (
            <p className="text-xs text-muted-foreground">
              {t("flights.total", { count: data.total })}
            </p>
          ) : null}
        </div>
        <Link href="/flights/new">
          <Button>
            <Plus className="h-4 w-4" />
            {t("flights.add")}
          </Button>
        </Link>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder={t("flights.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : null}

      {data && data.items.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          {t("flights.empty")}
        </p>
      ) : null}

      <div className="flex flex-col gap-3">
        {data?.items.map((flight) => (
          <Card key={flight.id}>
            <CardContent className="flex items-center justify-between gap-3 p-4">
              <Link href={`/flights/${flight.id}`} className="flex min-w-0 flex-1 items-center gap-3">
                <Plane className="h-5 w-5 shrink-0 text-primary" />
                <div className="min-w-0">
                  <div className="truncate font-medium">
                    {flight.origin ?? "—"} → {flight.destination ?? "—"}
                    {flight.service_number ? ` · ${flight.service_number}` : ""}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {formatDateTime(flight.departure_time)}
                    {flight.carrier ? ` · ${flight.carrier}` : ""}
                    {flight.seat ? ` · ${flight.seat}` : ""}
                  </div>
                </div>
              </Link>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleDelete(flight)}
                aria-label={t("common.delete")}
              >
                <Trash2 className="h-4 w-4 text-danger" />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
