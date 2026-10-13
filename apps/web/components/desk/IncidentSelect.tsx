"use client";

// The national desk has no "current" incident, but a report or a sheet the desk adds has to be filed under one.
// This is that one question: which disaster is it about? Shown only when the person can see more than one.

import type { Me } from "@/lib/api";

export function pickDefault(incidents: Me["incidents"]): string {
  return (incidents.find((i) => i.status === "active") ?? incidents[0])?.code ?? "";
}

export function IncidentSelect({ incidents, value, onChange }: { incidents: Me["incidents"]; value: string; onChange: (code: string) => void }) {
  if (incidents.length < 2) return null;
  return (
    <label className="block text-body">
      <span className="text-ink-2">Which disaster is this about?</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="field-compact mt-1 w-full">
        {incidents.filter((i) => i.status !== "closed").map((i) => <option key={i.code} value={i.code}>{i.name}</option>)}
      </select>
    </label>
  );
}
