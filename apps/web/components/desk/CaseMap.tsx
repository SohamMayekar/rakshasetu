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

function features(cases: Case[], dim: Set<number>) {
  return {
    type: "FeatureCollection" as const,
    features: cases.filter((c) => c.lat != null && c.lng != null && c.radius_m).map((c) => ({
      type: "Feature" as const,
      id: c.id,
      properties: { id: c.id, hue: dim.has(c.id) ? "#a1a1aa" : HUE[c.priority], low: c.location_confidence === "low" || c.location_confidence === "very_low",
                    dim: dim.has(c.id), label: c.public_id },
      geometry: { type: "Polygon" as const, coordinates: [ring(c.lat!, c.lng!, c.radius_m!)] },
    })),
  };
}

export function CaseMap({ cases, selected, dim = new Set(), onSelect }: {
  cases: Case[]; selected: number | null; dim?: Set<number>; onSelect: (id: number) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const ready = useRef(false);
  const fitted = useRef(false);
  const latest = useRef({ cases, selected, dim });
  latest.current = { cases, selected, dim };

  const [tilesDown, setTilesDown] = useState(false);

  useEffect(() => {
    let gone = false;
    let fallback: ReturnType<typeof setTimeout> | undefined;
    import("maplibre-gl").then(({ Map, NavigationControl }) => {
      if (gone || !box.current) return;
      const m = new Map({ container: box.current, style: STYLE, center: [84.39, 26.43], zoom: 9, attributionControl: { compact: false } });
      m.addControl(new NavigationControl({ showCompass: false }), "bottom-right");
      const toPaper = () => { if (!m.isStyleLoaded()) { setTilesDown(true); m.setStyle(BLANK); } };
      fallback = setTimeout(toPaper, 6000);
      m.on("error", (e) => { if (!ready.current && /styles|Failed to fetch/.test(String(e.error?.message))) toPaper(); });
      m.on("style.load", () => {   // fires for the tile style, or for the plain fallback
        clearTimeout(fallback);
        m.addSource("cases", { type: "geojson", data: features([], new Set()) });
        m.addLayer({ id: "fill", type: "fill", source: "cases", paint: { "fill-color": ["get", "hue"], "fill-opacity": ["case", ["get", "dim"], 0.03, 0.08] } });
        m.addLayer({ id: "line", type: "line", source: "cases", filter: ["!", ["get", "low"]],
                     paint: { "line-color": ["get", "hue"], "line-width": ["case", ["boolean", ["feature-state", "sel"], false], 3, 1.4] } });
        m.addLayer({ id: "line-low", type: "line", source: "cases", filter: ["get", "low"],
                     paint: { "line-color": ["get", "hue"], "line-dasharray": [2, 2],
                              "line-width": ["case", ["boolean", ["feature-state", "sel"], false], 3, 1.4] } });
        ready.current = true;
        prevSel.current = null;
        draw();
      });
      m.on("click", "fill", (e) => { const id = e.features?.[0]?.properties?.id; if (id != null) onSelectRef.current(Number(id)); });
      m.on("mouseenter", "fill", () => { m.getCanvas().style.cursor = "pointer"; });
      m.on("mouseleave", "fill", () => { m.getCanvas().style.cursor = ""; });
      map.current = m;
    });
    return () => { gone = true; clearTimeout(fallback); map.current?.remove(); map.current = null; ready.current = false; };
  }, []);

  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const prevSel = useRef<number | null>(null);

  function draw() {
    const m = map.current;
    if (!m || !ready.current) return;
    const { cases, selected, dim } = latest.current;
    (m.getSource("cases") as GeoJSONSource).setData(features(cases, dim));
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

  useEffect(() => {   // fly to the selected case, keeping its whole circle in view
    const c = cases.find((x) => x.id === selected);
    if (!map.current || !c || c.lat == null) return;
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
