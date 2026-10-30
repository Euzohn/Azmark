"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Backpack } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/**
 * "Belongs to trip" card shared by every record detail page, so the link back
 * to the trip looks identical for flights, trains and other transports.
 */
export function TripLinkCard({ tripId, label }: { tripId: string; label: string }) {
  const { t } = useI18n();
  const { data: trip } = useQuery({
    queryKey: ["trip", tripId],
    queryFn: () => api.getTrip(tripId),
  });

  return (
    <Link
      href={`/trips/${tripId}`}
      className="group flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-4 transition-colors hover:border-primary/40"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Backpack className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 truncate text-sm font-medium">{trip?.name ?? t("nav.trips")}</div>
      </div>
      <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}
