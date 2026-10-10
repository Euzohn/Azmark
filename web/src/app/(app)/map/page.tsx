"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useQuery } from "@tanstack/react-query";
import { MapIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GeoJSONSource, Map as MLMap, Marker, Popup, StyleSpecification } from "maplibre-gl";

import { useTheme } from "@/components/theme-provider";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
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
  const { t } = useI18n();
  const { theme } = useTheme();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const libRef = useRef<typeof import("maplibre-gl") | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const interactionsBoundRef = useRef(false);
  const themeRef = useRef(theme);
  const [ready, setReady] = useState(false);

  const { data, isLoading } = useQuery({
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
  const showMap = !isLoading && routes.length > 0;

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
      const lineFeatures = current.map((route) => {
        const from = pointOf(route.origin.code, route.origin.lat, route.origin.lon)!;
        const to = pointOf(route.destination.code, route.destination.lat, route.destination.lon)!;
        return {
          type: "Feature" as const,
          properties: {
            id: route.id,
            origin: route.origin.code,
            destination: route.destination.code,
            service: route.service_number ?? "",
            carrier: route.carrier ?? "",
          },
          geometry: { type: "LineString" as const, coordinates: greatCircle(from, to) },
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
      const accent = dark ? "#f0a46e" : "#9a4b1a";

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
            "circle-stroke-color": dark ? "#141416" : "#faf6ef",
            "circle-stroke-width": 1.5,
          },
        });

        if (!interactionsBoundRef.current) {
          interactionsBoundRef.current = true;
          map.on("click", "routes-line", (event) => {
            const feature = event.features?.[0];
            if (!feature) return;
            const props = feature.properties as Record<string, string>;
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

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-end justify-between gap-3">
        <h1 className="font-display text-3xl font-semibold tracking-tight">{t("map.title")}</h1>
        {data ? (
          <p className="text-sm text-muted-foreground">
            {t("map.routes", { count: routes.length })}
          </p>
        ) : null}
      </div>

      {isLoading ? <Skeleton className="h-[60vh] w-full" /> : null}

      {!isLoading && routes.length === 0 ? (
        <EmptyState icon={MapIcon} title={t("map.empty")} hint={t("map.emptyHint")} />
      ) : null}

      {showMap ? (
        <Card className="overflow-hidden p-0">
          <div ref={containerRef} className="h-[60vh] w-full" />
        </Card>
      ) : null}

      {showMap ? (
        <p className="text-xs text-muted-foreground">{t("map.greatCircleNote")}</p>
      ) : null}
    </div>
  );
}
