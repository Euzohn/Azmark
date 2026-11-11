"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useQuery } from "@tanstack/react-query";
import { MapIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  GeoJSONSource,
  Map as MLMap,
  MapLayerMouseEvent,
  Popup,
  StyleSpecification,
} from "maplibre-gl";

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
import { clusterByDistance, greatCircle, type LonLat } from "@/lib/geo";
import { useI18n } from "@/lib/i18n";
import type { MapRoute, PlaceType } from "@/lib/types";
import { cn } from "@/lib/utils";

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

type LayerFilter = "all" | "flights" | "ground" | "places" | "hotels";

// Colours mirror the map layers, so the filter row doubles as a legend.
const LAYER_FILTERS = [
  { value: "all", key: "map.layers.all" },
  { value: "flights", key: "map.layers.flights", dot: "bg-[#b45309] dark:bg-[#e0a737]" },
  { value: "ground", key: "map.layers.ground", dot: "bg-[#0f766e] dark:bg-[#61b8a8]" },
  { value: "places", key: "map.layers.places", dot: "bg-[#2563eb] dark:bg-[#7aa2f7]" },
  { value: "hotels", key: "map.layers.hotels", dot: "bg-[#c66b4e] dark:bg-[#d98a70]" },
] as const satisfies { value: LayerFilter; key: string; dot?: string }[];

// Stops closer than this collapse into one city-level label below DETAIL_ZOOM
// (Beijing South / West / main station are ~10 km apart). Above it, individual
// station names appear and MapLibre's collision detection hides the rest.
const CLUSTER_RADIUS_KM = 45;
const DETAIL_ZOOM = 7;

interface StopPoint {
  point: LonLat;
  label: string;
  // City identity used to label a low-zoom cluster. Airports expose both
  // spellings; stations only carry the Chinese city.
  cityKey: string | null;
  degree: number;
}

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
    // Raster styles carry no glyphs of their own, but the stop labels are
    // symbol layers. Point them at OpenFreeMap's font server (the same host
    // as the default vector styles) so text renders under a raster basemap.
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
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

function routeHref(route: MapRoute): string {
  if (route.type === "train") return `/trains/${route.id}`;
  if (route.type === "other") return `/transports/${route.id}`;
  return `/flights/${route.id}`;
}

function lineFeature(
  route: MapRoute,
  from: LonLat,
  to: LonLat,
  sag: number,
  side: 1 | -1,
  steps: number,
) {
  return {
    type: "Feature" as const,
    properties: {
      id: route.id,
      origin: route.origin.code ?? "",
      destination: route.destination.code ?? "",
      service: route.service_number ?? "",
      carrier: route.carrier ?? "",
    },
    geometry: {
      type: "LineString" as const,
      coordinates: greatCircle(from, to, steps, sag, side),
    },
  };
}

export default function MapPage() {
  const { t, locale } = useI18n();
  const { theme } = useTheme();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const libRef = useRef<typeof import("maplibre-gl") | null>(null);
  const popupRef = useRef<Popup | null>(null);
  // Feature-state highlight for the line under the cursor (desktop only).
  const hoverRef = useRef<{ source: "flights" | "ground"; id: string } | null>(null);
  const interactionsBoundRef = useRef(false);
  const themeRef = useRef(theme);
  const tRef = useRef(t);
  const layerRef = useRef<LayerFilter>("all");
  const fittedKeyRef = useRef("");
  const [ready, setReady] = useState(false);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [selectedHotelId, setSelectedHotelId] = useState<string | null>(null);
  const [selectedPlaceId, setSelectedPlaceId] = useState<string | null>(null);
  const [layer, setLayer] = useState<LayerFilter>("all");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["map-routes"],
    queryFn: api.getMapRoutes,
  });

  // Flight arcs and ground (train / other transport) lines are drawn as
  // separate sources so the map can tell them apart visually (spec #27).
  const flightRoutes = useMemo(
    () =>
      (data?.items ?? []).filter(
        (route) =>
          route.type === "flight" &&
          pointOf(route.origin.code, route.origin.lat, route.origin.lon) &&
          pointOf(route.destination.code, route.destination.lat, route.destination.lon),
      ),
    [data],
  );
  const groundRoutes = useMemo(
    () =>
      (data?.items ?? []).filter(
        (route) =>
          route.type !== "flight" &&
          pointOf(route.origin.code, route.origin.lat, route.origin.lon) &&
          pointOf(route.destination.code, route.destination.lat, route.destination.lon),
      ),
    [data],
  );
  const routes = useMemo(() => [...flightRoutes, ...groundRoutes], [flightRoutes, groundRoutes]);
  const hotels = useMemo(
    () =>
      (data?.hotels ?? []).filter(
        (hotel) => Number.isFinite(hotel.lat) && Number.isFinite(hotel.lon),
      ),
    [data],
  );
  const places = useMemo(
    () => (data?.places ?? []).filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lon)),
    [data],
  );
  const showMap =
    !isLoading &&
    !isError &&
    (routes.length > 0 || hotels.length > 0 || places.length > 0);

  const summary = useMemo(() => {
    const stops = new Set<string>();
    const countries = new Set<string>();
    let distance = 0;
    for (const route of routes) {
      if (route.origin.code) stops.add(route.origin.code);
      if (route.destination.code) stops.add(route.destination.code);
      if (route.origin.country) countries.add(route.origin.country);
      if (route.destination.country) countries.add(route.destination.country);
      if (route.distance_km) distance += route.distance_km;
    }
    return { stops: stops.size, countries: countries.size, distance };
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

  // Keep translations fresh for handlers bound once at map init.
  useEffect(() => {
    tRef.current = t;
  }, [t]);

  // Keep the layer filter available to the draw effect.
  useEffect(() => {
    layerRef.current = layer;
  }, [layer]);

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
      hoverRef.current = null;
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
      const active = layerRef.current;
      const showFlights = active === "all" || active === "flights";
      const showGround = active === "all" || active === "ground";
      const showPlaces = active === "all" || active === "places";
      const showHotels = active === "all" || active === "hotels";

      // A redraw (layer toggle, style swap, locale change) invalidates any
      // hover highlight — the feature it pointed at may be gone.
      if (hoverRef.current && map.getSource(hoverRef.current.source)) {
        map.setFeatureState(
          { source: hoverRef.current.source, id: hoverRef.current.id },
          { hover: false },
        );
      }
      hoverRef.current = null;

      // Group routes by unordered endpoint pair to detect overlapping arcs.
      // Round-trips (A→B and B→A) and duplicate routes share the same great
      // circle, so we fan them out: opposite directions curve to opposite
      // sides of the chord; same-direction routes get increasing sag so they
      // spread apart visually.
      const pairGroups = new Map<string, MapRoute[]>();
      for (const route of routes) {
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
        const reverse = group.filter((r) => (r.origin.code ?? "") > (r.destination.code ?? ""));
        forward.forEach((r, i) => {
          routeOffsets.set(r.id, { side: 1, sag: 2 + (i + 1) * 0.7 });
        });
        reverse.forEach((r, i) => {
          routeOffsets.set(r.id, { side: -1, sag: 2 + (i + 1) * 0.7 });
        });
      }

      const flightFeatures = showFlights
        ? flightRoutes.map((route) => {
            const from = pointOf(route.origin.code, route.origin.lat, route.origin.lon)!;
            const to = pointOf(
              route.destination.code,
              route.destination.lat,
              route.destination.lon,
            )!;
            const offset = routeOffsets.get(route.id);
            return lineFeature(route, from, to, offset?.sag ?? 2, offset?.side ?? 1, 96);
          })
        : [];
      // Ground lines stay close to the chord: rail routes are short enough that
      // the flight-style arc would read as a detour. minSagDeg 0 keeps the true
      // (near-straight) curve; the dashed style carries the distinction instead.
      const groundFeatures = showGround
        ? groundRoutes.map((route) => {
            const from = pointOf(route.origin.code, route.origin.lat, route.origin.lon)!;
            const to = pointOf(
              route.destination.code,
              route.destination.lat,
              route.destination.lon,
            )!;
            const offset = routeOffsets.get(route.id);
            return lineFeature(route, from, to, offset ? offset.sag * 0.3 : 0, offset?.side ?? 1, 48);
          })
        : [];

      // One stop per code, with the two label tiers the map needs: airports
      // keep their IATA code at detail zoom, stations their entered name.
      const stopMap = new Map<string, StopPoint>();
      for (const route of [
        ...(showFlights ? flightRoutes : []),
        ...(showGround ? groundRoutes : []),
      ]) {
        const isAirport = route.type === "flight";
        for (const end of [route.origin, route.destination]) {
          const coords = pointOf(end.code, end.lat, end.lon);
          if (!coords || !end.code) continue;
          const existing = stopMap.get(end.code);
          if (existing) {
            existing.degree += 1;
            continue;
          }
          stopMap.set(end.code, {
            point: coords,
            label: end.code,
            cityKey: isAirport ? (end.city_zh ?? end.city) : end.city,
            degree: 1,
          });
        }
      }
      const stops = Array.from(stopMap.values());

      // Airport city names come in both spellings; reuse them to localise the
      // Chinese city keys that stations carry.
      const cityZhToEn = new Map<string, string>();
      for (const route of routes) {
        if (route.type !== "flight") continue;
        for (const end of [route.origin, route.destination]) {
          if (end.city_zh && end.city) cityZhToEn.set(end.city_zh, end.city);
        }
      }
      const localizedCity = (key: string) =>
        locale === "zh-CN" ? key : (cityZhToEn.get(key) ?? key);

      // Low-zoom tier: nearby stops collapse into one city label so station
      // names never pile up at country/province zoom levels.
      const clusters = clusterByDistance(stops, CLUSTER_RADIUS_KM);
      const clusterFeatures = clusters.map((cluster) => {
        const cityKeys = new Set(
          cluster.members
            .map((member) => member.cityKey)
            .filter((key): key is string => key !== null),
        );
        const sharedCity = cityKeys.size === 1 ? [...cityKeys][0] : null;
        const top = [...cluster.members].sort((a, b) => b.degree - a.degree)[0]!;
        return {
          type: "Feature" as const,
          properties: {
            label: sharedCity ? localizedCity(sharedCity) : top.label,
            degree: cluster.members.reduce((sum, member) => sum + member.degree, 0),
          },
          geometry: { type: "Point" as const, coordinates: cluster.point },
        };
      });
      const stopFeatures = stops.map((stop) => ({
        type: "Feature" as const,
        properties: { label: stop.label, degree: stop.degree },
        geometry: { type: "Point" as const, coordinates: stop.point },
      }));

      const flightData = { type: "FeatureCollection" as const, features: flightFeatures };
      const groundData = { type: "FeatureCollection" as const, features: groundFeatures };
      const clusterData = { type: "FeatureCollection" as const, features: clusterFeatures };
      const stopData = { type: "FeatureCollection" as const, features: stopFeatures };

      // Geocoded stays render as pins beside the route lines (spec #10). Their
      // popup data rides in the feature properties so the click handler never
      // captures a stale `hotels` array.
      const hotelFeatures = (showHotels ? hotels : []).map((hotel) => ({
        type: "Feature" as const,
        properties: {
          id: hotel.id,
          name: hotel.name,
          check_in: hotel.check_in,
          check_out: hotel.check_out ?? "",
        },
        geometry: {
          type: "Point" as const,
          coordinates: [hotel.lon, hotel.lat] as LonLat,
        },
      }));
      const hotelData = { type: "FeatureCollection" as const, features: hotelFeatures };

      const placeFeatures = (showPlaces ? places : []).map((place) => ({
        type: "Feature" as const,
        properties: {
          id: place.id,
          name: place.name,
          place_type: place.type,
          city: place.city ?? "",
        },
        geometry: {
          type: "Point" as const,
          coordinates: [place.lon, place.lat] as LonLat,
        },
      }));
      const placeData = { type: "FeatureCollection" as const, features: placeFeatures };

      const dark = isDarkTheme(themeRef.current);
      const accent = dark ? "#e0a737" : "#b45309";
      const groundColor = dark ? "#61b8a8" : "#0f766e";
      const hotelColor = dark ? "#d98a70" : "#c66b4e";
      const placeColor = dark ? "#7aa2f7" : "#2563eb";
      const stroke = dark ? "#12161b" : "#f6f7f8";

      const labelColor = dark ? "#e5e7eb" : "#1f2937";

      if (!map.getSource("flights")) {
        // promoteId lets feature-state drive the hover highlight without a
        // second source: the route id is the feature id.
        map.addSource("flights", {
          type: "geojson",
          data: flightData,
          tolerance: 0,
          promoteId: "id",
        });
        map.addSource("ground", {
          type: "geojson",
          data: groundData,
          tolerance: 0,
          promoteId: "id",
        });
        map.addSource("stop-clusters", { type: "geojson", data: clusterData });
        map.addSource("stops", { type: "geojson", data: stopData });
        map.addSource("hotels", { type: "geojson", data: hotelData });
        map.addSource("places", { type: "geojson", data: placeData });
        map.addLayer({
          id: "flights-line",
          type: "line",
          source: "flights",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": accent,
            // Thin and faint at world zoom, heavier once you are close enough
            // to read individual routes — keeps dense bundles from turning
            // into a solid mass.
            "line-width": [
              "case",
              ["boolean", ["feature-state", "hover"], false],
              4,
              ["interpolate", ["linear"], ["zoom"], 2, 1, 6, 1.6, 10, 2.4],
            ],
            "line-opacity": [
              "case",
              ["boolean", ["feature-state", "hover"], false],
              1,
              ["interpolate", ["linear"], ["zoom"], 2, 0.45, 7, 0.85],
            ],
          },
        });
        map.addLayer({
          id: "ground-line",
          type: "line",
          source: "ground",
          layout: { "line-cap": "butt", "line-join": "round" },
          paint: {
            "line-color": groundColor,
            "line-width": [
              "case",
              ["boolean", ["feature-state", "hover"], false],
              4,
              ["interpolate", ["linear"], ["zoom"], 2, 1, 6, 1.5, 10, 2.2],
            ],
            "line-opacity": [
              "case",
              ["boolean", ["feature-state", "hover"], false],
              1,
              ["interpolate", ["linear"], ["zoom"], 2, 0.5, 7, 0.9],
            ],
            "line-dasharray": [2, 2],
          },
        });
        // Low zoom: one dot per city cluster, sized by how many routes pass
        // through it, so hubs stand out from one-off stops.
        map.addLayer({
          id: "stop-clusters-point",
          type: "circle",
          source: "stop-clusters",
          maxzoom: DETAIL_ZOOM,
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["get", "degree"],
              1,
              4,
              6,
              6.5,
              20,
              9,
            ],
            "circle-color": accent,
            "circle-stroke-color": stroke,
            "circle-stroke-width": 1.5,
          },
        });
        map.addLayer({
          id: "stops-point",
          type: "circle",
          source: "stops",
          minzoom: DETAIL_ZOOM,
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], DETAIL_ZOOM, 3, 12, 4.5],
            "circle-color": accent,
            "circle-stroke-color": stroke,
            "circle-stroke-width": 1.5,
          },
        });
        map.addLayer({
          id: "hotels-point",
          type: "circle",
          source: "hotels",
          paint: {
            "circle-radius": 5,
            "circle-color": hotelColor,
            "circle-stroke-color": stroke,
            "circle-stroke-width": 1.5,
          },
        });
        map.addLayer({
          id: "places-point",
          type: "circle",
          source: "places",
          paint: {
            "circle-radius": 4.5,
            "circle-color": placeColor,
            "circle-stroke-color": stroke,
            "circle-stroke-width": 1.5,
          },
        });
        // Symbol layers let MapLibre hide colliding labels for us instead of
        // stacking opaque DOM markers; variable anchors try several sides of
        // the dot before giving up. Busiest stops win the sort key.
        map.addLayer({
          id: "stop-clusters-label",
          type: "symbol",
          source: "stop-clusters",
          maxzoom: DETAIL_ZOOM,
          layout: {
            "text-field": ["get", "label"],
            "text-font": ["Noto Sans Regular"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 3, 10, DETAIL_ZOOM, 12],
            "text-variable-anchor": ["top", "bottom", "left", "right"],
            "text-radial-offset": 0.7,
            "text-justify": "auto",
            "text-padding": 2,
            "symbol-sort-key": ["-", ["get", "degree"]],
          },
          paint: {
            "text-color": labelColor,
            "text-halo-color": stroke,
            "text-halo-width": 1.4,
          },
        });
        map.addLayer({
          id: "stops-label",
          type: "symbol",
          source: "stops",
          minzoom: DETAIL_ZOOM,
          layout: {
            "text-field": ["get", "label"],
            "text-font": ["Noto Sans Regular"],
            "text-size": 11,
            "text-variable-anchor": ["top", "bottom", "left", "right"],
            "text-radial-offset": 0.7,
            "text-justify": "auto",
            "text-padding": 3,
            "symbol-sort-key": ["-", ["get", "degree"]],
          },
          paint: {
            "text-color": labelColor,
            "text-halo-color": stroke,
            "text-halo-width": 1.4,
          },
        });

        if (!interactionsBoundRef.current) {
          interactionsBoundRef.current = true;
          const routePopup = (event: MapLayerMouseEvent) => {
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
          };
          // Hover highlight: thicken and fully reveal the route under the
          // cursor, so a single line can be picked out of an overlapping bundle.
          const clearHover = () => {
            const hovered = hoverRef.current;
            if (!hovered) return;
            map.setFeatureState({ source: hovered.source, id: hovered.id }, { hover: false });
            hoverRef.current = null;
          };
          const bindHover = (
            lineLayer: "flights-line" | "ground-line",
            source: "flights" | "ground",
          ) => {
            map.on("mousemove", lineLayer, (event) => {
              const id = event.features?.[0]?.id;
              if (id === undefined || id === null) return;
              const next = String(id);
              if (hoverRef.current?.source === source && hoverRef.current.id === next) return;
              clearHover();
              hoverRef.current = { source, id: next };
              map.setFeatureState({ source, id: next }, { hover: true });
              map.getCanvas().style.cursor = "pointer";
            });
            map.on("mouseleave", lineLayer, () => {
              clearHover();
              map.getCanvas().style.cursor = "";
            });
            map.on("click", lineLayer, routePopup);
          };
          bindHover("flights-line", "flights");
          bindHover("ground-line", "ground");

          map.on("click", "hotels-point", (event) => {
            const feature = event.features?.[0];
            if (!feature) return;
            const props = feature.properties as Record<string, string>;
            if (window.matchMedia("(max-width: 767px)").matches) {
              setSelectedHotelId(props.id);
              return;
            }
            const node = document.createElement("div");
            node.className = "text-xs leading-relaxed";
            const title = document.createElement("a");
            title.className = "font-semibold underline-offset-2 hover:underline";
            title.href = `/hotels/${props.id}`;
            title.textContent = props.name;
            node.appendChild(title);
            const dates = [props.check_in, props.check_out].filter(Boolean).join(" → ");
            if (dates) {
              const subNode = document.createElement("div");
              subNode.textContent = dates;
              node.appendChild(subNode);
            }
            popupRef.current?.remove();
            popupRef.current = new maplibregl.Popup({ closeButton: false, offset: 8 })
              .setLngLat(event.lngLat)
              .setDOMContent(node)
              .addTo(map);
          });
          map.on("mouseenter", "hotels-point", () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", "hotels-point", () => {
            map.getCanvas().style.cursor = "";
          });

          map.on("click", "places-point", (event) => {
            const feature = event.features?.[0];
            if (!feature) return;
            const props = feature.properties as Record<string, string>;
            if (window.matchMedia("(max-width: 767px)").matches) {
              setSelectedPlaceId(props.id);
              return;
            }
            const node = document.createElement("div");
            node.className = "text-xs leading-relaxed";
            const title = document.createElement("a");
            title.className = "font-semibold underline-offset-2 hover:underline";
            title.href = `/places/${props.id}`;
            title.textContent = props.name;
            node.appendChild(title);
            const meta = [
              props.place_type
                ? tRef.current(`places.type.${props.place_type as PlaceType}`)
                : "",
              props.city,
            ]
              .filter(Boolean)
              .join(" · ");
            if (meta) {
              const subNode = document.createElement("div");
              subNode.textContent = meta;
              node.appendChild(subNode);
            }
            popupRef.current?.remove();
            popupRef.current = new maplibregl.Popup({ closeButton: false, offset: 8 })
              .setLngLat(event.lngLat)
              .setDOMContent(node)
              .addTo(map);
          });
          map.on("mouseenter", "places-point", () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", "places-point", () => {
            map.getCanvas().style.cursor = "";
          });
        }
      } else {
        (map.getSource("flights") as GeoJSONSource).setData(flightData);
        (map.getSource("ground") as GeoJSONSource).setData(groundData);
        (map.getSource("stop-clusters") as GeoJSONSource).setData(clusterData);
        (map.getSource("stops") as GeoJSONSource).setData(stopData);
        (map.getSource("hotels") as GeoJSONSource).setData(hotelData);
        (map.getSource("places") as GeoJSONSource).setData(placeData);
      }

      // Fit view from the FULL dataset (not the layer-filtered view) so
      // toggling layers never jumps the camera. Ground lines use near-chord
      // geometry; fitting their raw endpoints is enough.
      const boundsCoords: LonLat[] = [
        ...flightRoutes.flatMap((route) => [
          pointOf(route.origin.code, route.origin.lat, route.origin.lon)!,
          pointOf(route.destination.code, route.destination.lat, route.destination.lon)!,
        ]),
        ...groundRoutes.flatMap((route) => [
          pointOf(route.origin.code, route.origin.lat, route.origin.lon)!,
          pointOf(route.destination.code, route.destination.lat, route.destination.lon)!,
        ]),
        ...hotels.map((hotel) => [hotel.lon, hotel.lat] as LonLat),
        ...places.map((place) => [place.lon, place.lat] as LonLat),
      ];
      const fittedKey = `${routes.length}|${hotels.length}|${places.length}`;
      if (boundsCoords.length > 0 && fittedKey !== fittedKeyRef.current) {
        fittedKeyRef.current = fittedKey;
        let minLon = Infinity;
        let minLat = Infinity;
        let maxLon = -Infinity;
        let maxLat = -Infinity;
        for (const [lon, lat] of boundsCoords) {
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
          {
            padding: 64,
            maxZoom: routes.length > 0 ? 6 : 10,
            duration: 600,
          },
        );
      }

    };

    draw();
    map.on("style.load", draw);
    return () => {
      map.off("style.load", draw);
    };
  }, [routes, flightRoutes, groundRoutes, hotels, places, ready, layer, locale]);

  const selectedRoute = routes.find((route) => route.id === selectedRouteId);
  const selectedHotel = hotels.find((hotel) => hotel.id === selectedHotelId);
  const selectedPlace = places.find((place) => place.id === selectedPlaceId);
  const subtitle = !data
    ? undefined
    : hotels.length > 0 || places.length > 0
      ? t("map.subtitle", {
          routes: routes.length,
          hotels: hotels.length,
          places: places.length,
        })
      : t("map.routes", { count: routes.length });

  const hasGround = groundRoutes.length > 0;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("map.title")} subtitle={subtitle} />

      {isLoading ? <Skeleton className="h-[60vh] w-full" /> : null}

      {isError ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-xl border border-danger/30 bg-card p-5"
        >
          <span className="text-sm text-danger">{t("common.error")}</span>
          <Button variant="outline" onClick={() => void refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      ) : null}

      {!isLoading && !isError && routes.length === 0 && hotels.length === 0 && places.length === 0 ? (
        <EmptyState icon={MapIcon} title={t("map.empty")} hint={t("map.emptyHint")} />
      ) : null}

      {showMap && !isError ? (
        <>
          {routes.length > 0 ? (
            <div className="grid grid-cols-2 gap-4 border-y border-border py-4 sm:grid-cols-4">
              <Stat label={t("map.stats.routes")} value={routes.length} />
              <Stat label={t("map.stats.stops")} value={summary.stops} />
              <Stat label={t("map.stats.countries")} value={summary.countries} />
              <Stat
                label={t("map.stats.distance")}
                value={t("map.km", { value: numberFormat.format(summary.distance) })}
              />
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2" role="group" aria-label={t("map.layers")}>
            {LAYER_FILTERS.map((item) => (
              <Button
                key={item.value}
                size="sm"
                variant={layer === item.value ? "default" : "outline"}
                onClick={() => setLayer(item.value)}
                className="gap-1.5"
              >
                {"dot" in item ? (
                  <span
                    aria-hidden
                    className={cn("h-2 w-2 shrink-0 rounded-full", item.dot)}
                  />
                ) : null}
                {t(item.key)}
              </Button>
            ))}
          </div>

          <div
            className={`grid gap-4 ${
              longestRoutes.length > 0 ? "xl:grid-cols-[minmax(0,1fr)_20rem]" : ""
            }`}
          >
            <Card className="overflow-hidden p-0">
              <div ref={containerRef} className="h-[55dvh] min-h-[24rem] w-full xl:h-[70dvh]" />
            </Card>
            {longestRoutes.length > 0 ? (
              <Card className="xl:max-h-[70dvh] xl:overflow-y-auto">
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
                            {[route.service_number, route.carrier].filter(Boolean).join(" · ")}
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
              </Card>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground">
            {t("map.coverageHint")} {t("map.greatCircleNote")}
            {hasGround ? ` ${t("map.groundNote")}` : ""}
            {routes.length > 0 ? ` ${t("map.zoomHint")}` : ""}
          </p>
          <BottomSheet
            open={selectedRoute !== undefined}
            onClose={() => setSelectedRouteId(null)}
            title={t("map.title")}
          >
            {selectedRoute ? (
              <Link
                href={routeHref(selectedRoute)}
                onClick={() => setSelectedRouteId(null)}
                className="flex items-center justify-between gap-4 rounded-lg border border-border p-4 text-sm font-medium"
              >
                <span>
                  {selectedRoute.origin.code ?? selectedRoute.origin.name} →{" "}
                  {selectedRoute.destination.code ?? selectedRoute.destination.name}
                </span>
                <span className="text-xs text-muted-foreground">{selectedRoute.service_number}</span>
              </Link>
            ) : null}
          </BottomSheet>
          <BottomSheet
            open={selectedHotel !== undefined}
            onClose={() => setSelectedHotelId(null)}
            title={t("hotels.detail")}
          >
            {selectedHotel ? (
              <Link
                href={`/hotels/${selectedHotel.id}`}
                onClick={() => setSelectedHotelId(null)}
                className="flex items-center justify-between gap-4 rounded-lg border border-border p-4 text-sm font-medium"
              >
                <span className="min-w-0 truncate">{selectedHotel.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {[selectedHotel.check_in, selectedHotel.check_out].filter(Boolean).join(" → ")}
                </span>
              </Link>
            ) : null}
          </BottomSheet>
          <BottomSheet
            open={selectedPlace !== undefined}
            onClose={() => setSelectedPlaceId(null)}
            title={t("places.title")}
          >
            {selectedPlace ? (
              <Link
                href={`/places/${selectedPlace.id}`}
                onClick={() => setSelectedPlaceId(null)}
                className="flex items-center justify-between gap-4 rounded-lg border border-border p-4 text-sm font-medium"
              >
                <span className="min-w-0 truncate">{selectedPlace.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {t(`places.type.${selectedPlace.type}`)}
                </span>
              </Link>
            ) : null}
          </BottomSheet>
        </>
      ) : null}
    </div>
  );
}
