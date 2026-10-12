"use client";

// A map of India with each live incident as a circle (PRD F-C1). Same tiles and plain-paper fallback as the desk.

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef } from "react";

const STYLE = "https://tiles.openfreemap.org/styles/positron";
const BLANK = { version: 8 as const, sources: {}, layers: [{ id: "paper", type: "background" as const, paint: { "background-color": "#f3f3f1" } }] };

export type Pin = { code: string; name: string; lat: number; lng: number; broken: boolean };

export function IncidentsMap({ pins, onOpen }: { pins: Pin[]; onOpen: (code: string) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const open = useRef(onOpen);
  open.current = onOpen;
  useEffect(() => {
    let gone = false;
    let m: import("maplibre-gl").Map | undefined;
    import("maplibre-gl").then(({ Map }) => {
      if (gone || !box.current) return;
      m = new Map({ container: box.current, style: STYLE, bounds: [[68, 7], [97.5, 35.5]], attributionControl: { compact: true } });
      const fallback = setTimeout(() => { if (!m!.isStyleLoaded()) m!.setStyle(BLANK); }, 6000);
      m.on("style.load", () => {
        clearTimeout(fallback);
        // International boundaries on this overview come from OpenStreetMap, not the Survey of India; this screen
        // doesn't need them, so it doesn't draw them.
        for (const l of m!.getStyle().layers ?? []) if (/boundary/i.test(l.id)) m!.setLayoutProperty(l.id, "visibility", "none");
        m!.addSource("inc", { type: "geojson", data: { type: "FeatureCollection", features: pins.map((p) => ({
          type: "Feature" as const, properties: { code: p.code, label: `${p.code} · ${p.name}`, broken: p.broken },
          geometry: { type: "Point" as const, coordinates: [p.lng, p.lat] } })) } });
        m!.addLayer({ id: "dot", type: "circle", source: "inc", paint: { "circle-radius": 9, "circle-color": ["case", ["get", "broken"], "#111111", "#ffffff"],
                                                                       "circle-stroke-color": "#111111", "circle-stroke-width": 2 } });
        m!.addLayer({ id: "label", type: "symbol", source: "inc", layout: { "text-field": ["get", "label"], "text-offset": [0, 1.4],
                                                                          "text-size": 12, "text-font": ["Noto Sans Regular"] },
                      paint: { "text-color": "#111111", "text-halo-color": "#ffffff", "text-halo-width": 1.5 } });
        m!.on("click", "dot", (e) => { const code = e.features?.[0]?.properties?.code; if (code) open.current(String(code)); });
      });
    });
    return () => { gone = true; m?.remove(); };
  }, [pins]);
  return <div ref={box} className="h-full min-h-72 w-full" aria-label="Map of India with the live incidents" />;
}
