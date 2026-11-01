"use client";

import { useState } from "react";

import { TripLinkCard } from "@/components/trip-link-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Hotel } from "@/lib/types";

const STATUS_VARIANT: Record<string, "neutral" | "success" | "danger"> = {
  scheduled: "neutral",
  completed: "success",
  cancelled: "danger",
};

export function HotelSummary({ hotel }: { hotel: Hotel }) {
  const { t } = useI18n();
  const [showRef, setShowRef] = useState(false);

  const nights =
    hotel.check_in && hotel.check_out
      ? Math.round(
          (new Date(hotel.check_out).getTime() - new Date(hotel.check_in).getTime()) /
            (1000 * 60 * 60 * 24),
        )
      : null;

  const fields: [TranslationKey, string | null][] = [
    ["hotels.checkIn", hotel.check_in],
    ["hotels.checkOut", hotel.check_out],
    ["hotels.roomType", hotel.room_type],
    ["hotels.roomNumber", hotel.room_number],
    ["hotels.price", hotel.price != null ? `${hotel.price} ${hotel.currency ?? ""}`.trim() : null],
    ["hotels.address", hotel.address],
  ];

  return (
    <>
      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 md:px-7">
          <div className="min-w-0">
            <div className="font-display text-lg font-semibold tracking-tight">{hotel.hotel}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">
              {hotel.check_in}
              {hotel.check_out ? ` → ${hotel.check_out}` : ""}
              {nights ? ` · ${t("hotels.nights", { count: nights })}` : ""}
            </div>
          </div>
          <Badge variant={STATUS_VARIANT[hotel.status] ?? "neutral"}>
            {t(`hotels.status.${hotel.status}` as TranslationKey)}
          </Badge>
        </div>
        <dl className="grid gap-x-6 gap-y-3 px-5 py-5 sm:grid-cols-2 md:px-7">
          {fields.map(([key, value]) => (
            <div key={key} className="flex flex-col gap-0.5">
              <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {t(key)}
              </dt>
              <dd className="text-sm text-foreground">{value || "—"}</dd>
            </div>
          ))}
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {t("hotels.bookingRef")}
            </dt>
            <dd className="text-sm text-foreground">
              {hotel.booking_reference ? (
                <>
                  <span className="tabular-nums">
                    {showRef ? hotel.booking_reference : "••••••"}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="ml-2 h-6 px-2 text-xs"
                    onClick={() => setShowRef((v) => !v)}
                  >
                    {showRef ? t("common.hide") : t("common.show")}
                  </Button>
                </>
              ) : (
                "—"
              )}
            </dd>
          </div>
        </dl>
        {hotel.notes ? (
          <p className="border-t border-border px-5 py-4 text-sm text-muted-foreground md:px-7">
            {hotel.notes}
          </p>
        ) : null}
      </section>
      {hotel.trip_id ? <TripLinkCard tripId={hotel.trip_id} label={t("hotels.trip")} /> : null}
    </>
  );
}