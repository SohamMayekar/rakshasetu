"use client";

// The call-taker's form (PRD F-L1): type the call, or paste a forwarded message. As they type, the keyword
// rules (no AI, nothing stored) show what they read, as chips, so the call-taker can ask for what's missing
// ("how many people?", "which village?"). Saving writes the report first; the case appears a moment later,
// through the same pipeline as every other channel. The form's id is its idempotency key: a double click or a
// retry can never make two reports.

import { useEffect, useRef, useState } from "react";

import { Button, Chip } from "@/components/ui";
import { api, type Me } from "@/lib/api";

import { word } from "./Facts";
import { IncidentSelect } from "./IncidentSelect";

type Preview = { summary: string; extraction: {
  people_count?: { value: number; kind: string }; hazards?: { type: string }[]; needs?: { type: string }[];
  vulnerable?: { type: string }[]; location?: { village_or_locality?: { latin: string }; district?: string;
  landmarks?: { type: string; name?: string }[] }; callback_phone?: string;
} };

const newId = () => (globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`);

export function NewReport({ incident: initial, incidents, onSaved, onClose }: {
  incident: string; incidents: Me["incidents"]; onSaved: (reportId: number) => void; onClose: () => void;
}) {
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [forward, setForward] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const clientId = useRef(newId());
  const [incident, setIncident] = useState(initial);

  useEffect(() => {   // live chips, 300 ms after the last keystroke
    if (!text.trim()) { setPreview(null); return; }
    const t = setTimeout(() => {
      api<Preview>("/v1/ingest/desk/preview", { method: "POST", json: { text } }).then(setPreview).catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [text]);

  const ex = preview?.extraction;
  const chips: string[] = [];
  if (ex?.people_count) chips.push(`${ex.people_count.kind === "estimated" ? "~" : ""}${ex.people_count.value} people`);
  ex?.hazards?.forEach((h) => chips.push(word(h.type)));
  ex?.needs?.forEach((n) => chips.push(word(n.type)));
  ex?.vulnerable?.forEach((v) => chips.push(word(v.type)));
  ex?.location?.landmarks?.forEach((l) => chips.push(`${l.name ? l.name + " " : ""}${word(l.type)}`));
  if (ex?.location?.village_or_locality) chips.push(ex.location.village_or_locality.latin);
  const missing = [!ex?.people_count && "how many people", !(ex?.location?.village_or_locality || ex?.location?.landmarks?.length) && "where"]
    .filter(Boolean) as string[];

  const save = async (form: FormData) => {
    setSaving(true); setError(null);
    try {
      const r = await api<{ report_id: number }>("/v1/ingest/desk", { method: "POST", json: {
        incident, text, client_id: clientId.current, phone: String(form.get("phone") || "") || null,
        reporter_name: String(form.get("name") || "") || null, relation: String(form.get("relation") || "unknown"),
        pasted_forward: forward } });
      onSaved(r.report_id);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); setSaving(false); }
  };

  if (incidents.length === 0) {
    return (
      <aside className="panel-in fixed inset-0 z-40 flex flex-col bg-paper p-6 md:static md:h-full md:w-[440px] md:shrink-0 md:rounded-card md:border md:border-line/80 md:shadow-[var(--shadow-card)]" aria-label="New report">
        <div className="flex items-center justify-between"><h2 className="text-lg font-semibold tracking-tight">New report</h2><Button variant="quiet" size="sm" onClick={onClose}>Close</Button></div>
        <p className="mt-4 text-body text-ink-2">There is no incident to file this under yet. Start one on the <a className="font-semibold underline underline-offset-4" href="/desk/incidents">Incidents</a> page, then come back.</p>
      </aside>
    );
  }
  return (
    <aside className="panel-in fixed inset-0 z-40 flex flex-col overflow-hidden bg-paper md:static md:h-full md:w-[440px] md:shrink-0 md:rounded-card md:border md:border-line/80 md:shadow-[var(--shadow-card)]" aria-label="New report">
      <div className="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 className="text-lg font-semibold tracking-tight">New report</h2>
        <Button variant="quiet" size="sm" onClick={onClose}>Close</Button>
      </div>
      <form className="flex-1 space-y-4 overflow-y-auto px-5 py-4" onSubmit={(e) => { e.preventDefault(); save(new FormData(e.currentTarget)); }}>
        <IncidentSelect incidents={incidents} value={incident} onChange={setIncident} />
        <label className="block">
          <span className="text-body text-ink-2">What did they say? Type the call, or paste a forwarded message.</span>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} required autoFocus
                    placeholder="In Ward 12, behind the primary school, near the bridge, 6 people are trapped on the first floor…"
                    className="field mt-1 leading-snug" />
        </label>
        <div aria-live="polite" className="min-h-14">
          {chips.length > 0 && (
            <p className="flex flex-wrap items-center gap-1.5">
              <span className="text-small text-ink-2">Heard so far:</span>
              {chips.map((c, i) => <Chip key={i}>{c}</Chip>)}

            </p>
          )}
          {text.trim() && missing.length > 0 && <p className="mt-1.5 text-small text-ink-2">Ask: {missing.join(" · ")}?</p>}
        </div>
        <label className="flex items-center gap-2 text-body">
          <input type="checkbox" checked={forward} onChange={(e) => setForward(e.target.checked)} />
          This is a forwarded message (the sender may not be there)
        </label>
        <div className="grid grid-cols-2 gap-3 text-body">
          <label className="block"><span className="text-ink-2">Phone to call back</span>
            <input name="phone" inputMode="tel" placeholder="98765 43210" className="field-compact mt-1 w-full tabular" /></label>
          <label className="block"><span className="text-ink-2">Name (optional)</span>
            <input name="name" className="field-compact mt-1 w-full" /></label>
          {!forward && (
            <label className="col-span-2 block"><span className="text-ink-2">Who is calling</span>
              <select name="relation" defaultValue="unknown" className="field-compact mt-1 w-full">
                <option value="unknown">Not said</option><option value="self">The person in danger</option><option value="family">Family</option>
                <option value="neighbour">Neighbour</option><option value="volunteer">Volunteer</option><option value="official">Official</option>
              </select></label>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Button variant="primary" type="submit" disabled={saving || !text.trim()}>{saving ? "Saving…" : "Save report"}</Button>
        </div>
        {error && <p className="rounded-md bg-wash px-2 py-1 text-small">{error}</p>}
      </form>
    </aside>
  );
}
