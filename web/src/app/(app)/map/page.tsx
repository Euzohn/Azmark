"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useQuery } from "@tanstack/react-query";
import { MapIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GeoJSONSource, Map as MLMap, Marker, Popup, StyleSpecification } from "maplibre-gl";

import { useTheme } from "@/components/theme-provider";
import { AirportName } from "@/components/airport-name";
import { PageHeader } from "@/components/page-header";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Stat } from "@/components/ui/stat";
import { api } from "@/lib/api";
import { greatCircle, type LonLat } from "@/lib/geo";
import { useI18n } from "@/lib/i18n";

// Basemap defaults to OpenFreeMap — a free, keyless, no-watermark vector map.
// Override per build with:
//   NEXT_PUBLIC_MAP_STYLE_LIGHT / NEXT_PUBLIC_MAP_STYLE_DARK  (vector style URLs)
//   NEXT_PUBLIC_MAP_TILES_LIGHT / NEXT_PUBLIC_MAP_TILES_DARK  (raster {z}/{x}/{y} templates)
// The raster override wins when set, which is handy for region-specific providers.
const STYLE_LIGHT =
  process.env.NEXT_PUBLIC_MAP_STYLE_LIGHT ?? "https://tiles.openfreemap.org/styles/positron";
const STYLE_DARK =
  process.env.NEXT_PUBLIC_MAP_STYLE_DARK ?? "https://tiles.openfreemap.org/styles/dark";
const TILES_LIGHT = process.env.NEXT_PUBLIC_MAP_TILES_LIGHT;
const TILES_DARK = process.env.NEXT_PUBLIC_MAP_TILES_DARK;

const ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function isDarkTheme(theme: string): boolean {
  if (theme === "dark") return true;
  if (theme === "light") return false;
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

function rasterStyle(tiles: string): StyleSpecification {
  return {
    version: 8,
    sources: {
      basemap: { type: "raster", tiles: [tiles], tileSize: 256, attribution: ATTRIBUTION },
    },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  };
}

function styleFor(theme: string): string | StyleSpecification {
  const dark = isDarkTheme(theme);
  const tiles = dark ? TILES_DARK : TILES_LIGHT;
  if (tiles) return rasterStyle(tiles);
  return dark ? STYLE_DARK : STYLE_LIGHT;
}

function pointOf(code: string | null, lat: number | null, lon: number | null): LonLat | null {
  if (!code || lat === null || lon === null) return null;
  return [lon, lat];
}

export default function MapPage() {
  const { t, locale } = useI18n();
  const { theme } = useTheme();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const libRef = useRef<typeof import("maplibre-gl") | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const interactionsBoundRef = useRef(false);
  const themeRef = useRef(theme);
  const [ready, setReady] = useState(false);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["map-routes"],
    queryFn: api.getMapRoutes,
  });

  const routes = useMemo(
    () =>
      (data?.items ?? []).filter(
        (route) =>
          pointOf(route.origin.code, route.origin.lat, route.origin.lon) &&
          pointOf(route.destination.code, route.destination.lat, route.destination.lon),
      ),
    [data],
  );
  const showMap = !isLoading && !isError && routes.length > 0;

  const summary = useMemo(() => {
    const airports = new Set<string>();
    const countries = new Set<string>();
    let distance = 0;
    for (const route of routes) {
      if (route.origin.code) airports.add(route.origin.code);
      if (route.destination.code) airports.add(route.destination.code);
      if (route.origin.country) countries.add(route.origin.country);
      if (route.destination.country) countries.add(route.destination.country);
      if (route.distance_km) distance += route.distance_km;
    }
    return { airports: airports.size, countries: countries.size, distance };
  }, [routes]);

  const longestRoutes = useMemo(
    () =>
      routes
        .filter((route) => route.distance_km !== null)
        .sort((a, b) => (b.distance_km ?? 0) - (a.distance_km ?? 0))
        .slice(0, 5),
    [routes],
  );

  const numberFormat = useMemo(
    () => new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }),
    [locale],
  );

  // Keep the latest theme available to the (mount-only) map effects.
  useEffect(() => {
    themeRef.current = theme;
  }, [theme]);

  // Initialise the map once the container is on screen (client-only).
  useEffect(() => {
    if (!showMap) return;
    const container = containerRef.current;
    if (!container || mapRef.current) return;
    let cancelled = false;

    void (async () => {
      const maplibregl = await import("maplibre-gl");
      if (cancelled || !containerRef.current) return;
      libRef.current = maplibregl;

      // Webpack can only emit the worker as an asset when the specifier is a
      // literal; MapLibre's internal runtime URL is dynamic and 404s in prod,
      // so point it at the emitted file explicitly (vector tiles need it).
      maplibregl.setWorkerUrl(
        new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).href,
      );

      const map = new maplibregl.Map({
        container,
        style: styleFor(themeRef.current),
        center: [30, 25],
        zoom: 1.3,
        attributionControl: { compact: true },
      });
      mapRef.current = map;
      map.on("load", () => {
        if (!cancelled) setReady(true);
      });
    })();

    return () => {
      cancelled = true;
      interactionsBoundRef.current = false;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      popupRef.current?.remove();
      popupRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
      setReady(false);
    };
  }, [showMap]);

  // Swap the basemap when the colour theme changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setStyle(styleFor(theme));
  }, [theme, ready]);

  // Draw routes whenever the data changes or a (new) style finishes loading.
  useEffect(() => {
    const map = mapRef.current;
    const maplibregl = libRef.current;
    if (!map || !maplibregl || !ready) return;

    const draw = () => {
      const current = routes;

      // Group routes by unordered airport pair to detect overlapping arcs.
      // Round-trip flights (A→B and B→A) and duplicate routes share the same
      // great circle, so we fan them out: opposite directions curve to
      // opposite sides of the chord; same-direction routes get increasing
      // sag so they spread apart visually.
      const pairGroups = new Map<string, typeof current>();
      for (const route of current) {
        const codes = [route.origin.code, route.destination.code]
          .filter(Boolean)
          .sort() as string[];
        const key = codes.join("|");
        const group = pairGroups.get(key);
        if (group) group.push(route);
        else pairGroups.set(key, [route]);
      }
      const routeOffsets = new Map<string, { side: 1 | -1; sag: number }>();
      for (const group of pairGroups.values()) {
        if (group.length <= 1) continue;
        const forward = group.filter(
          (r) => (r.origin.code ?? "") <= (r.destination.code ?? ""),
        );
        const reverse = group.filter(
          (r) => (r.origin.code ?? "") > (r.destination.code ?? ""),
        );
        forward.forEach((r, i) => {
          routeOffsets.set(r.id, { side: 1, sag: 2 + (i + 1) * 0.7 });
        });
        reverse.forEach((r, i) => {
          routeOffsets.set(r.id, { side: -1, sag: 2 + (i + 1) * 0.7 });
        });
      }

      const lineFeatures = current.map((route) => {
        const from = pointOf(route.origin.code, route.origin.lat, route.origin.lon)!;
        const to = pointOf(route.destination.code, route.destination.lat, route.destination.lon)!;
        const offset = routeOffsets.get(route.id);
        const side = offset?.side ?? 1;
        const sag = offset?.sag ?? 2;
        return {
          type: "Feature" as const,
          properties: {
            id: route.id,
            origin: route.origin.code,
            destination: route.destination.code,
            service: route.service_number ?? "",
            carrier: route.carrier ?? "",
          },
          geometry: { type: "LineString" as const, coordinates: greatCircle(from, to, 96, sag, side) },
        };
      });

      const airportMap = new Map<string, LonLat>();
      for (const route of current) {
        const from = pointOf(route.origin.code, route.origin.lat, route.origin.lon);
        const to = pointOf(route.destination.code, route.destination.lat, route.destination.lon);
        if (from && route.origin.code) airportMap.set(route.origin.code, from);
        if (to && route.destination.code) airportMap.set(route.destination.code, to);
      }
      const pointFeatures = Array.from(airportMap.entries()).map(([code, coords]) => ({
        type: "Feature" as const,
        properties: { code },
        geometry: { type: "Point" as const, coordinates: coords },
      }));

      const lineData = { type: "FeatureCollection" as const, features: lineFeatures };
      const pointData = { type: "FeatureCollection" as const, features: pointFeatures };

      const dark = isDarkTheme(themeRef.current);
      const accent = dark ? "#e0a737" : "#b45309";

      if (!map.getSource("routes")) {
        map.addSource("routes", { type: "geojson", data: lineData, tolerance: 0 });
        map.addSource("airports", { type: "geojson", data: pointData });
        map.addLayer({
          id: "routes-line",
          type: "line",
          source: "routes",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": accent, "line-width": 2, "line-opacity": 0.8 },
        });
        map.addLayer({
          id: "airports-point",
          type: "circle",
          source: "airports",
          paint: {
            "circle-radius": 3.5,
            "circle-color": accent,
             "circle-stroke-color": dark ? "#12161b" : "#f6f7f8",
            "circle-stroke-width": 1.5,
          },
        });

        if (!interactionsBoundRef.current) {
          interactionsBoundRef.current = true;
          map.on("click", "routes-line", (event) => {
            const feature = event.features?.[0];
            if (!feature) return;
             const props = feature.properties as Record<string, string>;
             if (window.matchMedia("(max-width: 767px)").matches) {
               setSelectedRouteId(props.id);
               return;
             }
            const node = document.createElement("div");
            node.className = "text-xs leading-relaxed";
            const title = document.createElement("div");
            title.className = "font-semibold";
            title.textContent = `${props.origin} → ${props.destination}`;
            node.appendChild(title);
            const sub = [props.service, props.carrier].filter(Boolean).join(" · ");
            if (sub) {
              const subNode = document.createElement("div");
              subNode.textContent = sub;
              node.appendChild(subNode);
            }
            popupRef.current?.remove();
            popupRef.current = new maplibregl.Popup({ closeButton: false, offset: 8 })
              .setLngLat(event.lngLat)
              .setDOMContent(node)
              .addTo(map);
          });
          map.on("mouseenter", "routes-line", () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", "routes-line", () => {
            map.getCanvas().style.cursor = "";
          });
        }
      } else {
        (map.getSource("routes") as GeoJSONSource).setData(lineData);
        (map.getSource("airports") as GeoJSONSource).setData(pointData);
      }

      // airport code labels
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      for (const [code, coords] of airportMap.entries()) {
        const el = document.createElement("div");
        el.className =
          "ml-3 rounded-md border border-border bg-card/90 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-foreground shadow-sm";
        el.textContent = code;
        const marker = new maplibregl.Marker({ element: el, anchor: "left" })
          .setLngLat(coords)
          .addTo(map);
        markersRef.current.push(marker);
      }

      // fit view to the drawn routes
      if (lineFeatures.length > 0) {
        const coords: LonLat[] = lineFeatures.flatMap(
          (feature) => feature.geometry.coordinates as LonLat[],
        );
        let minLon = Infinity;
        let minLat = Infinity;
        let maxLon = -Infinity;
        let maxLat = -Infinity;
        for (const [lon, lat] of coords) {
          minLon = Math.min(minLon, lon);
          maxLon = Math.max(maxLon, lon);
          minLat = Math.min(minLat, lat);
          maxLat = Math.max(maxLat, lat);
        }
        map.fitBounds(
          [
            [minLon, minLat],
            [maxLon, maxLat],
          ],
          { padding: 64, maxZoom: 6, duration: 600 },
        );
      }
    };

    draw();
    map.on("style.load", draw);
    return () => {
      map.off("style.load", draw);
    };
  }, [routes, ready]);

  const routeHref = (route: (typeof routes)[number]) => route.type === "train" ? `/trains/${route.id}` : route.type === "other" ? `/transports/${route.id}` : `/flights/${route.id}`;
  const selectedRoute = routes.find((route) => route.id === selectedRouteId);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("map.title")}
        subtitle={data ? t("map.routes", { count: routes.length }) : undefined}
      />

      {isLoading ? <Skeleton className="h-[60vh] w-full" /> : null}

      {isError ? <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-danger/30 bg-card p-5"><span className="text-sm text-danger">{t("common.error")}</span><Button variant="outline" onClick={() => void refetch()}>{t("common.retry")}</Button></div> : null}

      {!isLoading && !isError && routes.length === 0 ? (
        <EmptyState icon={MapIcon} title={t("map.empty")} hint={t("map.emptyHint")} />
      ) : null}

      {showMap && !isError ? (
        <>
          <div className="grid grid-cols-2 gap-4 border-y border-border py-4 sm:grid-cols-4">
            <Stat label={t("map.stats.routes")} value={routes.length} />
            <Stat label={t("map.stats.airports")} value={summary.airports} />
            <Stat label={t("map.stats.countries")} value={summary.countries} />
            <Stat
              label={t("map.stats.distance")}
              value={t("map.km", { value: numberFormat.format(summary.distance) })}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
            <Card className="overflow-hidden p-0"><div ref={containerRef} className="h-[55dvh] min-h-[24rem] w-full xl:h-[70dvh]" /></Card>
            {longestRoutes.length > 0 ? <Card className="xl:max-h-[70dvh] xl:overflow-y-auto">
              <CardHeader>
                <CardTitle>{t("map.longest")}</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
                {longestRoutes.map((route) => {
                  return (
                    <Link
                      key={route.id}
                      href={routeHref(route)}
                      className="flex items-center justify-between gap-3 rounded-xl border border-border/70 px-3 py-2.5 transition-colors hover:bg-accent/40"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 truncate text-sm font-medium">
                          <AirportName value={route.origin.code ?? route.origin.name} />
                          <span className="text-muted-foreground">→</span>
                          <AirportName
                            value={route.destination.code ?? route.destination.name}
                          />
                        </div>
                        <div className="mt-0.5 truncate text-xs text-muted-foreground">
                          {[route.service_number, route.carrier]
                            .filter(Boolean)
                            .join(" · ")}
                        </div>
                      </div>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {t("map.km", {
                          value: numberFormat.format(route.distance_km ?? 0),
                        })}
                      </span>
                    </Link>
                  );
                })}
              </CardContent>
            </Card> : null}
          </div>
          <p className="text-xs text-muted-foreground">{t("map.coverageHint")} {t("map.greatCircleNote")}</p>
          <BottomSheet open={selectedRoute !== undefined} onClose={() => setSelectedRouteId(null)} title={t("map.title")}>
            {selectedRoute ? <Link href={routeHref(selectedRoute)} onClick={() => setSelectedRouteId(null)} className="flex items-center justify-between gap-4 rounded-lg border border-border p-4 text-sm font-medium">
              <span>{selectedRoute.origin.code ?? selectedRoute.origin.name} → {selectedRoute.destination.code ?? selectedRoute.destination.name}</span>
              <span className="text-xs text-muted-foreground">{selectedRoute.service_number}</span>
            </Link> : null}
          </BottomSheet>
        </>
      ) : null}
    </div>
  );
}
