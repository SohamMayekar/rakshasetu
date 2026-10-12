"use client";

// The desk map (PRD F-C2, F-L4): MapLibre + OpenFreeMap Positron (free, no key, © OpenStreetMap contributors).
// Every case is a CIRCLE whose radius is the honest uncertainty; never a bare pin. Dashed = Low. The stroke's
// hue is the case's priority (the only thing hue means). Cases with no location aren't drawn: they're in
// the queue as "needs location".

import "maplibre-gl/dist/maplibre-gl.css";

import type { GeoJSONSource, Map as MlMap } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import type { Case } from "@/lib/api";

const STYLE = "https://tiles.openfreemap.org/styles/positron";
// If the venue network can't reach the tile server, the circles still draw, on plain paper.
const BLANK = { version: 8 as const, sources: {}, layers: [{ id: "paper", type: "background" as const, paint: { "background-color": "#f3f3f1" } }] };
const HUE: Record<string, string> = { P1: "#c62828", P2: "#d97706", P3: "#52525b", P4: "#a1a1aa" };

function ring(lat: number, lng: number, metres: number, steps = 48): [number, number][] {
  const out: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    const dLat = (metres * Math.cos(a)) / 111_320;
    const dLng = (metres * Math.sin(a)) / (111_320 * Math.cos((lat * Math.PI) / 180));
    out.push([lng + dLng, lat + dLat]);
  }
  return out;
}

// A normal incident draws every case as its honest circle at every zoom. In a surge (more than MANY placed
// cases) the circles only start at street-ish zoom; further out, nearby cases gather into grey bubbles with a
// count, and a lone case is still a circle of its true size (at least 4 px), hollow when its place is uncertain.
// That keeps thousands of cases cheap to draw without ever showing a bare pin.
const MANY = 300;
const CIRCLES_FROM_ZOOM = 11;
const SURGE_REFRESH_MS = 5000;
const EARTH = 40_075_016.686;

function points(cases: Case[], dim: Set<number>) {
  return {
    type: "FeatureCollection" as const,
    features: cases.filter((c) => c.lat != null && c.lng != null).map((c) => ({
      type: "Feature" as const, id: c.id,
      properties: { id: c.id, hue: dim.has(c.id) ? "#a1a1aa" : HUE[c.priority],
                    low: c.location_confidence === "low" || c.location_confidence === "very_low",
                    k: ((c.radius_m ?? 300) * 512) / (EARTH * Math.cos((c.lat! * Math.PI) / 180)) },   // px at zoom 0
      geometry: { type: "Point" as const, coordinates: [c.lng!, c.lat!] },
    })),
  };
}

// circle-radius in pixels for the true radius: k * 2^zoom, never under 4 px
const TRUE_SIZE = ["interpolate", ["exponential", 2], ["zoom"],
  ...[5, 7, 9, 11].flatMap((z) => [z, ["max", 4, ["*", ["get", "k"], 2 ** z]]])] as unknown as number;

// A case's ring is 64 points of trigonometry; a surge re-sends thousands of cases every second, so each case
// object keeps its ring (a refetched case is a new object and gets a new one).
const rings = new WeakMap<Case, number[][]>();

function features(cases: Case[], dim: Set<number>) {
  return {
    type: "FeatureCollection" as const,
    features: cases.filter((c) => c.lat != null && c.lng != null && c.radius_m).map((c) => {
      let r = rings.get(c);
      if (!r) { r = ring(c.lat!, c.lng!, c.radius_m!); rings.set(c, r); }
      return {
        type: "Feature" as const,
        id: c.id,
        properties: { id: c.id, hue: dim.has(c.id) ? "#a1a1aa" : HUE[c.priority], low: c.location_confidence === "low" || c.location_confidence === "very_low",
                      dim: dim.has(c.id), label: c.public_id },
        geometry: { type: "Polygon" as const, coordinates: [r] },
      };
    }),
  };
}

export function CaseMap({ cases, selected, dim = new Set(), onSelect, picking = false, picked = null, onPick }: {
  cases: Case[]; selected: number | null; dim?: Set<number>; onSelect: (id: number) => void;
  picking?: boolean; picked?: { lat: number; lng: number } | null; onPick?: (p: { lat: number; lng: number }) => void;
}) {
  const pickRef = useRef({ picking, onPick });
  pickRef.current = { picking, onPick };
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const ready = useRef(false);
  const fitted = useRef(false);
  const latest = useRef({ cases, selected, dim });
  latest.current = { cases, selected, dim };

  const [tilesDown, setTilesDown] = useState(false);
  const resizeObs = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    let gone = false;
    let fallback: ReturnType<typeof setTimeout> | undefined;
    import("maplibre-gl").then(({ Map, NavigationControl }) => {
      if (gone || !box.current) return;
      const m = new Map({ container: box.current, style: STYLE, center: [84.39, 26.43], zoom: 9, attributionControl: { compact: false },
                            fadeDuration: 0 });   // no label fades: each one is a run of repaints
      m.addControl(new NavigationControl({ showCompass: false }), "bottom-right");
      const toPaper = () => { if (!m.isStyleLoaded()) { setTilesDown(true); m.setStyle(BLANK); } };
      fallback = setTimeout(toPaper, 6000);
      m.on("error", (e) => { if (!ready.current && /styles|Failed to fetch/.test(String(e.error?.message))) toPaper(); });
      m.on("style.load", () => {   // fires for the tile style, or for the plain fallback
        clearTimeout(fallback);
        m.addSource("cases", { type: "geojson", data: features([], new Set()) });
        m.addSource("pts", { type: "geojson", data: points([], new Set()), cluster: true, clusterRadius: 36, clusterMaxZoom: CIRCLES_FROM_ZOOM - 1 });
        m.addLayer({ id: "fill", type: "fill", source: "cases",
                     paint: { "fill-color": ["get", "hue"], "fill-opacity": ["case", ["get", "dim"], 0.03, 0.08] } });
        m.addLayer({ id: "line", type: "line", source: "cases", filter: ["!", ["get", "low"]],
                     paint: { "line-color": ["get", "hue"], "line-width": ["case", ["boolean", ["feature-state", "sel"], false], 3, 1.4] } });
        m.addLayer({ id: "line-low", type: "line", source: "cases", filter: ["get", "low"],
                     paint: { "line-color": ["get", "hue"], "line-dasharray": [2, 2],
                              "line-width": ["case", ["boolean", ["feature-state", "sel"], false], 3, 1.4] } });
        m.addLayer({ id: "dot", type: "circle", source: "pts", maxzoom: CIRCLES_FROM_ZOOM, filter: ["!", ["has", "point_count"]],
                     layout: { visibility: "none" },
                     paint: { "circle-color": ["get", "hue"], "circle-radius": TRUE_SIZE, "circle-opacity": ["case", ["get", "low"], 0, 0.15],
                              "circle-stroke-color": ["get", "hue"], "circle-stroke-width": 1.4 } });
        m.addLayer({ id: "cluster", type: "circle", source: "pts", maxzoom: CIRCLES_FROM_ZOOM, filter: ["has", "point_count"],
                     layout: { visibility: "none" },
                     paint: { "circle-color": "#ffffff", "circle-stroke-color": "#8a8a8a", "circle-stroke-width": 1.5,
                              "circle-radius": ["step", ["get", "point_count"], 11, 10, 14, 100, 18, 1000, 22] } });
        if (m.getStyle().glyphs) m.addLayer({ id: "cluster-count", type: "symbol", source: "pts", maxzoom: CIRCLES_FROM_ZOOM, filter: ["has", "point_count"],
                     layout: { visibility: "none", "text-field": ["get", "point_count_abbreviated"], "text-size": 11,
                               "text-font": ["Noto Sans Regular"], "text-allow-overlap": true },
                     paint: { "text-color": "#111111" } });
        m.on("click", "cluster", async (e) => {   // a cluster zooms in to what it holds
          const f = e.features?.[0];
          if (!f) return;
          const zoom = await (m.getSource("pts") as GeoJSONSource).getClusterExpansionZoom(Number(f.properties?.cluster_id));
          m.easeTo({ center: (f.geometry as GeoJSON.Point).coordinates as [number, number], zoom });
        });
        m.addSource("pick", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        m.addLayer({ id: "pick", type: "line", source: "pick", paint: { "line-color": "#111111", "line-width": 2 } });
        ready.current = true;
        prevSel.current = null;
        drawn.current = null;
        draw();
      });
      m.on("click", (e) => {   // in "Move pin" mode, a click places the pin; otherwise it selects a circle
        if (pickRef.current.picking) { pickRef.current.onPick?.({ lat: e.lngLat.lat, lng: e.lngLat.lng }); return; }
        const hit = m.queryRenderedFeatures(e.point, { layers: ["fill", "dot"] })[0];
        if (hit?.properties?.id != null) onSelectRef.current(Number(hit.properties.id));
      });
      m.on("zoomend", () => { if (drawn.current && !drawn.current.rings) draw(); });   // surge: circles once zoomed in
      m.on("mouseenter", "fill", () => { if (!pickRef.current.picking) m.getCanvas().style.cursor = "pointer"; });
      m.on("mouseleave", "fill", () => { m.getCanvas().style.cursor = pickRef.current.picking ? "crosshair" : ""; });
      map.current = m;
      // The drawer opening or closing changes the map's width: keep the camera centred on what it should show.
      const ro = new ResizeObserver(() => m.resize());
      ro.observe(box.current);
      resizeObs.current = ro;
    });
    return () => { gone = true; clearTimeout(fallback); if (later.current) clearTimeout(later.current); resizeObs.current?.disconnect(); map.current?.remove(); map.current = null; ready.current = false; };
  }, []);

  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const prevSel = useRef<number | null>(null);

  const drawn = useRef<{ cases: Case[]; dim: Set<number>; many: boolean; rings: boolean } | null>(null);
  const lastPush = useRef(0);
  const later = useRef<ReturnType<typeof setTimeout> | null>(null);

  function draw() {
    const m = map.current;
    if (!m || !ready.current) return;
    const { cases, selected, dim } = latest.current;
    const changed = drawn.current?.cases !== cases || drawn.current?.dim !== dim;
    const many = changed && cases.filter((c) => c.lat != null).length > MANY;
    const since = performance.now() - lastPush.current;
    if (changed && many && drawn.current?.many && since < SURGE_REFRESH_MS) {
      // A surge changes the cases every second; the map (an overview: the queue is where work happens) follows
      // every 5 s, so the browser isn't repainting the whole map all the time.
      later.current ??= setTimeout(() => { later.current = null; draw(); }, SURGE_REFRESH_MS - since);
    } else if (changed) {   // rebuild only what changed
      lastPush.current = performance.now();
      if (many) (m.getSource("pts") as GeoJSONSource).setData(points(cases, dim));
      for (const id of ["fill", "line", "line-low"]) m.setLayerZoomRange(id, many ? CIRCLES_FROM_ZOOM : 0, 24);
      for (const id of ["dot", "cluster", "cluster-count"]) if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", many ? "visible" : "none");
      drawn.current = { cases, dim, many, rings: false };
    }
    // The circles: always in a normal incident; in a surge only once zoomed in far enough to show them.
    const d = drawn.current;
    if (d && !d.rings && (!d.many || m.getZoom() >= CIRCLES_FROM_ZOOM - 0.5)) {
      (m.getSource("cases") as GeoJSONSource).setData(features(d.cases, d.dim));
      d.rings = true;
    }
    if (prevSel.current != null) m.setFeatureState({ source: "cases", id: prevSel.current }, { sel: false });
    if (selected != null) m.setFeatureState({ source: "cases", id: selected }, { sel: true });
    prevSel.current = selected;
    const placed = cases.filter((c) => c.lat != null && c.location_confidence !== "very_low");
    const sel = cases.find((c) => c.id === selected && c.lat != null);
    if (!fitted.current && sel) {
      const r = (sel.radius_m ?? 300) * 3, dLat = r / 111_320, dLng = r / (111_320 * Math.cos((sel.lat! * Math.PI) / 180));
      m.fitBounds([[sel.lng! - dLng, sel.lat! - dLat], [sel.lng! + dLng, sel.lat! + dLat]], { duration: 0, maxZoom: 16 });
      fitted.current = true;
    } else if (!fitted.current && placed.length) {
      const lats = placed.map((c) => c.lat!), lngs = placed.map((c) => c.lng!);
      m.fitBounds([[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]], { padding: 60, duration: 0, maxZoom: 13 });
      fitted.current = true;
    }
  }

  useEffect(draw, [cases, selected, dim]);

  useEffect(() => {   // the pin being placed: a 50 m circle (a person placed it)
    const m = map.current;
    if (!m || !ready.current) return;
    m.getCanvas().style.cursor = picking ? "crosshair" : "";
    const data = picked ? { type: "FeatureCollection" as const, features: [{ type: "Feature" as const, properties: {},
      geometry: { type: "Polygon" as const, coordinates: [ring(picked.lat, picked.lng, 50)] } }] } : { type: "FeatureCollection" as const, features: [] };
    (m.getSource("pick") as GeoJSONSource | undefined)?.setData(data);
  }, [picking, picked]);

  useEffect(() => {   // fly to the selected case, keeping its whole circle in view
    const c = cases.find((x) => x.id === selected);
    if (!map.current || !c || c.lat == null) return;
    map.current.resize();
    const r = (c.radius_m ?? 300) * 3;
    const dLat = r / 111_320, dLng = r / (111_320 * Math.cos((c.lat * Math.PI) / 180));
    map.current.fitBounds([[c.lng! - dLng, c.lat - dLat], [c.lng! + dLng, c.lat + dLat]], { duration: 500, maxZoom: 16 });
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="relative h-full w-full">
      <div ref={box} className="h-full w-full" aria-label="Map of cases: each circle is where the household may be" />
      {tilesDown && <p className="absolute left-3 top-3 rounded-md bg-paper/90 px-2 py-1 text-xs text-ink-2 shadow-sm">Map tiles unavailable: circles only</p>}
    </div>
  );
}
