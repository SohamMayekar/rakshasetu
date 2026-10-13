"use client";

// Sensors: the live numbers partners' instruments send (a river gauge, a rain gauge), read against two lines
// the partner sets. They are context for a person beside the cases they are near, and never change a case's
// priority. Anything the demo sends is labelled "Simulated" on the card.

import { Gauge } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Filters, IncidentPage, useMe } from "@/components/desk/IncidentPage";
import { Card, Chip, Empty, ago, useNow } from "@/components/ui";
import { api } from "@/lib/api";

type Sensor = {
  id: number; code: string; name: string; kind: string; unit: string; state: "unknown" | "ok" | "warn" | "danger";
  last_value: number | null; last_read_at: string | null; warn_at: number | null; danger_at: number | null;
  simulated: boolean; partner: string | null; incident: string; incident_name: string; district: string | null;
  lat: number | null; lng: number | null; trend: number[];
};

const STATE = {
  danger: { shape: "▲", word: "Danger", tone: "attention" as const },
  warn: { shape: "◆", word: "Rising", tone: "neutral" as const },
  ok: { shape: "●", word: "Normal", tone: "quiet" as const },
  unknown: { shape: "○", word: "No reading", tone: "quiet" as const },
};
const KIND: Record<string, string> = { water_level: "Water level", rainfall: "Rainfall", wind: "Wind", temperature: "Temperature", other: "Sensor" };

// A small line of the last readings, with the two lines the partner set drawn across it.
function Trend({ values, warn, danger }: { values: number[]; warn: number | null; danger: number | null }) {
  if (values.length < 2) return <div className="h-12 rounded-inner bg-wash" aria-hidden />;
  const all = [...values, ...[warn, danger].filter((v): v is number => v != null)];
  const lo = Math.min(...all), hi = Math.max(...all), span = hi - lo || 1;
  const y = (v: number) => 44 - ((v - lo) / span) * 40;
  const x = (i: number) => (i / (values.length - 1)) * 200;
  const path = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  return (
    <svg viewBox="0 0 200 48" className="h-12 w-full rounded-inner bg-wash" role="img" aria-label={`Last ${values.length} readings`} preserveAspectRatio="none">
      {warn != null && <line x1="0" x2="200" y1={y(warn)} y2={y(warn)} stroke="#8c8a85" strokeDasharray="3 4" />}
      {danger != null && <line x1="0" x2="200" y1={y(danger)} y2={y(danger)} stroke="#151515" strokeDasharray="6 3" />}
      <path d={path} fill="none" stroke="#151515" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export default function Sensors() {
  const me = useMe();
  const now = useNow(30_000);
  const [sensors, setSensors] = useState<Sensor[] | null>(null);
  const [filter, setFilter] = useState<"all" | "danger" | "warn" | "ok">("all");

  useEffect(() => {
    const load = () => api<Sensor[]>("/v1/telemetry").then(setSensors).catch(() => setSensors([]));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const counts = useMemo(() => {
    const n = { all: 0, danger: 0, warn: 0, ok: 0 };
    for (const s of sensors ?? []) { n.all++; if (s.state in n) n[s.state as "danger" | "warn" | "ok"]++; }
    return n;
  }, [sensors]);
  const shown = (sensors ?? []).filter((s) => filter === "all" || s.state === filter);

  return (
    <IncidentPage me={me} title="Sensors" sub="live numbers from partners’ instruments, beside the families they may affect">
      <Filters value={filter} onChange={setFilter} items={[
        { key: "all", label: "All", count: counts.all }, { key: "danger", label: "Danger", count: counts.danger },
        { key: "warn", label: "Rising", count: counts.warn }, { key: "ok", label: "Normal", count: counts.ok }]} />
      <div className="mt-4">
        {!sensors ? <Card><Empty>Loading…</Empty></Card> : shown.length === 0 ? (
          <Card><Empty>{sensors.length === 0
            ? "No sensors yet. A partner’s instruments appear here after their first signed reading."
            : "Nothing at this level right now."}</Empty></Card>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {shown.map((s) => {
              const st = STATE[s.state];
              return (
                <li key={s.id}>
                  <Card className={`h-full p-4 ${s.state === "danger" ? "ring-2 ring-ink" : ""}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="flex items-center gap-1.5 text-small text-ink-3"><Gauge className="size-3.5" aria-hidden />{KIND[s.kind] ?? "Sensor"} · {s.incident}</p>
                        <h2 className="truncate text-heading font-semibold">{s.name}</h2>
                        <p className="truncate text-small text-ink-2">{s.district ?? s.incident_name}</p>
                      </div>
                      <Chip tone={st.tone}><span aria-hidden className="mr-1">{st.shape}</span>{st.word}</Chip>
                    </div>
                    <p className="tabular mt-3 text-[1.75rem] font-semibold leading-none">
                      {s.last_value ?? "–"}<span className="ml-1 text-body font-normal text-ink-2">{s.unit}</span>
                    </p>
                    <div className="mt-3"><Trend values={s.trend} warn={s.warn_at} danger={s.danger_at} /></div>
                    <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-small text-ink-3">
                      <span>{s.last_read_at ? `read ${ago(s.last_read_at, now)}` : "not read yet"}</span>
                      {s.warn_at != null && <span>rising at {s.warn_at}</span>}
                      {s.danger_at != null && <span>danger at {s.danger_at}</span>}
                      {s.simulated && <Chip tone="quiet" title="Sent by a demonstration script, not a real instrument">Simulated</Chip>}
                    </p>
                  </Card>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </IncidentPage>
  );
}
