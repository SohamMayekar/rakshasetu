"use client";

// Incidents: the lifecycle of every disaster the platform is handling, for the national admin. A new disaster is
// a form, not a deployment: it gets its own districts and its own case numbers and starts receiving reports at
// once. Every change asks for a reason and goes on the audit trail.

import { Plus, Siren } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { IncidentPage, useMe } from "@/components/desk/IncidentPage";
import { Button, Card, Chip, Empty } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

type Inc = { id: number; code: string; name: string; type: string; states: string[]; status: string; districts: string[] };

const STATUS: Record<string, string> = { draft: "Draft", active: "Active", standing_down: "Standing down", closed: "Closed" };
const NEXT: Record<string, { to: string; label: string }[]> = {
  draft: [{ to: "active", label: "Start" }],
  active: [{ to: "standing_down", label: "Stand down" }],
  standing_down: [{ to: "active", label: "Reopen" }, { to: "closed", label: "Close" }],
  closed: [],
};
const TYPES = ["flood", "cyclone", "landslide", "fire", "collapse", "accident", "other"];

function say(e: unknown): string {
  if (e instanceof ApiError) {
    if (Array.isArray(e.detail)) return e.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || "Check the form and try again.";
    return String(e.detail);
  }
  return e instanceof Error ? e.message : String(e);
}

function Row({ i, onChanged }: { i: Inc; onChanged: () => void }) {
  const [to, setTo] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const go = async () => {
    if (!to) return;
    setBusy(true); setError(null);
    try {
      await api(`/v1/incidents/${i.id}`, { method: "PATCH", json: { status: to, reason: reason.trim() } });
      setTo(null); setReason(""); onChanged();
    } catch (e) { setError(say(e)); }
    setBusy(false);
  };
  return (
    <li className="px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-body font-semibold"><span className="tabular rounded-md bg-wash px-1.5 text-small">{i.code}</span>{i.name}</p>
          <p className="mt-0.5 text-small text-ink-2">{i.type} · {i.states.join(", ")} · {i.districts.length} district{i.districts.length === 1 ? "" : "s"}</p>
        </div>
        <div className="flex items-center gap-2">
          <Chip tone={i.status === "active" ? "attention" : "neutral"}>{STATUS[i.status] ?? i.status}</Chip>
          {NEXT[i.status]?.map((n) => (
            <Button key={n.to} size="sm" variant={to === n.to ? "primary" : "secondary"} onClick={() => { setTo(to === n.to ? null : n.to); setError(null); }}>{n.label}</Button>
          ))}
        </div>
      </div>
      {to && (
        <form className="mt-3 flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); void go(); }}>
          <input value={reason} onChange={(e) => setReason(e.target.value)} autoFocus placeholder="Why? (a few words, kept on the audit trail)"
                 className="field min-w-0 flex-1" />
          <Button variant="primary" type="submit" disabled={busy || reason.trim().length < 3}>{busy ? "Saving…" : `Confirm: ${STATUS[to]}`}</Button>
        </form>
      )}
      {error && <p className="mt-2 rounded-md bg-wash px-2 py-1 text-small">{error}</p>}
    </li>
  );
}

function NewIncident({ onCreated }: { onCreated: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (form: FormData) => {
    setError(null);
    const num = (k: string) => Number(String(form.get(k) ?? "").trim());
    const lat = num("lat"), lng = num("lng");
    const states = String(form.get("states") ?? "").split(",").map((s) => s.trim()).filter(Boolean);
    // one district per line: "Name, State, lat, lng"
    const districts = String(form.get("districts") ?? "").split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
      const [name, state, la, lo] = l.split(",").map((p) => p.trim());
      return { name, state, centroid: [Number(la), Number(lo)] as [number, number] };
    });
    if (Number.isNaN(lat) || Number.isNaN(lng)) return setError("The centre needs a latitude and a longitude.");
    if (!districts.length || districts.some((d) => !d.name || !d.state || d.centroid.some(Number.isNaN))) {
      return setError("Each district goes on its own line: name, state, latitude, longitude.");
    }
    setBusy(true);
    try {
      await api("/v1/incidents", { method: "POST", json: {
        code: String(form.get("code") ?? "").trim().toUpperCase(), name: String(form.get("name") ?? "").trim(),
        type: String(form.get("type") ?? "other"), states, center: [lat, lng], districts, status: "active" } });
      onCreated();
    } catch (e) { setError(say(e)); }
    setBusy(false);
  };
  const field = "field mt-1";
  return (
    <form className="grid gap-3 p-4 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); void submit(new FormData(e.currentTarget)); }}>
      <label className="block text-body"><span className="text-ink-2">Short code (2 to 4 letters)</span>
        <input name="code" required maxLength={4} pattern="[A-Za-z]{2,4}" placeholder="KL" className={`${field} uppercase`} /></label>
      <label className="block text-body"><span className="text-ink-2">Type</span>
        <select name="type" defaultValue="flood" className={`${field} bg-paper`}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></label>
      <label className="block text-body md:col-span-2"><span className="text-ink-2">Name</span>
        <input name="name" required minLength={3} placeholder="Kerala floods" className={field} /></label>
      <label className="block text-body md:col-span-2"><span className="text-ink-2">States, separated by commas</span>
        <input name="states" required placeholder="Kerala" className={field} /></label>
      <label className="block text-body"><span className="text-ink-2">Centre latitude</span>
        <input name="lat" required inputMode="decimal" placeholder="10.85" className={`${field} tabular`} /></label>
      <label className="block text-body"><span className="text-ink-2">Centre longitude</span>
        <input name="lng" required inputMode="decimal" placeholder="76.27" className={`${field} tabular`} /></label>
      <label className="block text-body md:col-span-2"><span className="text-ink-2">Districts, one per line: name, state, latitude, longitude</span>
        <textarea name="districts" required rows={3} placeholder={"Thrissur, Kerala, 10.52, 76.21\nPalakkad, Kerala, 10.78, 76.65"}
                  className="field mt-1 tabular" /></label>
      <div className="flex items-center gap-3 md:col-span-2">
        <Button variant="primary" type="submit" disabled={busy}><Plus className="size-4" aria-hidden />{busy ? "Creating…" : "Create and start"}</Button>
        <span className="text-small text-ink-3">It starts receiving reports straight away. Nothing else needs changing.</span>
      </div>
      {error && <p className="rounded-md bg-wash px-2 py-1 text-small md:col-span-2">{error}</p>}
    </form>
  );
}

export default function Incidents() {
  const me = useMe();
  const [list, setList] = useState<Inc[] | null>(null);
  const [adding, setAdding] = useState(false);
  const load = useCallback(() => { api<Inc[]>("/v1/incidents").then(setList).catch(() => setList([])); }, []);
  useEffect(load, [load]);
  const admin = !!me?.permissions.includes("incident.admin");

  return (
    <IncidentPage me={me} title="Incidents" sub="every disaster the platform is handling, from start to close"
                  aside={admin ? <Button variant="primary" onClick={() => setAdding((a) => !a)}><Plus className="size-4" aria-hidden />New incident</Button> : undefined}>
      {adding && admin && (
        <Card className="mb-4">
          <h2 className="border-b border-line px-4 py-3 text-heading font-semibold">Start a new incident</h2>
          <NewIncident onCreated={() => { setAdding(false); load(); }} />
        </Card>
      )}
      <Card className="overflow-hidden">
        {!list ? <Empty>Loading…</Empty> : list.length === 0 ? <Empty>{admin ? "Nothing here yet. Start your first incident with “New incident”: a name, a centre and its districts." : "No incidents yet. The national admin starts them."}</Empty> : (
          <ul className="divide-y divide-line">
            {list.map((i) => admin ? <Row key={i.id} i={i} onChanged={load} /> : (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-4">
                <p className="flex items-center gap-2 text-body font-semibold"><Siren className="size-4" aria-hidden />{i.name}</p>
                <Chip tone={i.status === "active" ? "attention" : "neutral"}>{STATUS[i.status] ?? i.status}</Chip>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {!admin && <p className="mt-3 text-small text-ink-3">Only the national admin can start, stand down or close an incident.</p>}
    </IncidentPage>
  );
}
