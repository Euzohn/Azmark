/**
 * Year attribution for the map's year filter (spec #27).
 *
 * Routes belong to their departure year in the departure timezone — the same
 * rule the Wrapped report uses — so a New Year's Eve flight lands in the year
 * it actually departed. Hotels use the check-in date; photos carry no zone and
 * follow the browser-local display used on the photo pages. Places have no
 * time dimension and are never year-filtered.
 */
import type { MapHotel, MapPhoto, MapRoute } from "@/lib/types";

import { zonedDateKey } from "./datetime.ts";

type RouteLike = Pick<MapRoute, "departure_time" | "departure_timezone">;
type HotelLike = Pick<MapHotel, "check_in">;
type PhotoLike = Pick<MapPhoto, "captured_at">;

/** Departure-local year of a route, or null when it has no usable time. */
export function routeYear(route: RouteLike): number | null {
  const key = zonedDateKey(route.departure_time, route.departure_timezone);
  return key === "unknown" ? null : Number(key.slice(0, 4));
}

/** Check-in year of a stay, or null when the date is missing/malformed. */
export function hotelYear(hotel: HotelLike): number | null {
  const year = Number((hotel.check_in ?? "").slice(0, 4));
  return Number.isInteger(year) && year > 0 ? year : null;
}

/** Browser-local capture year of a photo, matching the photo pages' display. */
export function photoYear(photo: PhotoLike): number | null {
  if (!photo.captured_at) return null;
  const date = new Date(photo.captured_at);
  return Number.isNaN(date.getTime()) ? null : date.getFullYear();
}

/** Distinct years present in the map payload, newest first. */
export function mapYears(
  data:
    | { items?: RouteLike[]; hotels?: HotelLike[]; photos?: PhotoLike[] }
    | undefined,
): number[] {
  const years = new Set<number>();
  for (const route of data?.items ?? []) {
    const year = routeYear(route);
    if (year !== null) years.add(year);
  }
  for (const hotel of data?.hotels ?? []) {
    const year = hotelYear(hotel);
    if (year !== null) years.add(year);
  }
  for (const photo of data?.photos ?? []) {
    const year = photoYear(photo);
    if (year !== null) years.add(year);
  }
  return [...years].sort((a, b) => b - a);
}