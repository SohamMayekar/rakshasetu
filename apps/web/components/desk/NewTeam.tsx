"use client";

// Add a team: who they are, what they can do (a catalog for every kind of disaster), where they are based and,
// if they carry the team app, their lead's sign-in. Nothing is pre-filled for any city or district: the lists come
// from the incidents this deployment has started.

import { Check, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui";
import { api, ApiError, type Me } from "@/lib/api";

type Catalog = { capabilities: { key: string; label: string; group: string; for: string }[]; agencies: string[] };
const RADIO = ["VHF", "HAM", "satellite", "phone"];

function say(e: unknown): string {
  if (e instanceof ApiError) {
    if (Array.isArray(e.detail)) return e.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || "Check the form and try again.";
    return String(e.detail);
  }
  return e instanceof Error ? e.message : String(e);
}

export function NewTeam({ me, onCreated }: { me: Me | null; onCreated: (note: string) => void }) {
  const [cat, setCat] = useState<Catalog | null>(null);
  const incidents = useMemo(() => (me?.incidents ?? []).filter((i) => i.status !== "closed"), [me]);
  const [incident, setIncident] = useState("");
  const [agency, setAgency] = useState("Fire & Rescue");
  const [other, setOther] = useState("");
  const [caps, setCaps] = useState<string[]>([]);
  const [hasApp, setHasApp] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api<Catalog>("/v1/teams/catalog").then(setCat).catch(() => setCat(null)); }, []);
  useEffect(() => { if (!incident && incidents[0]) setIncident(incidents[0].code); }, [incidents, incident]);

  const districts = (me?.districts ?? []).filter((d) => incidents.find((i) => i.code === incident)?.id === d.incident_id);
  const groups = useMemo(() => {
    const g = new Map<string, Catalog["capabilities"]>();
    for (const c of cat?.capabilities ?? []) g.set(c.group, [...(g.get(c.group) ?? []), c]);
    return [...g.entries()];
  }, [cat]);

  const toggle = (k: string) => setCaps((c) => (c.includes(k) ? c.filter((x) => x !== k) : [...c, k]));

  const submit = async (form: FormData) => {
    setError(null);
    const num = (k: string) => { const v = String(form.get(k) ?? "").trim(); return v === "" ? null : Number(v); };
    const lat = num("lat"), lng = num("lng");
    if ((lat === null) !== (lng === null) || Number.isNaN(lat) || Number.isNaN(lng)) return setError("Give both latitude and longitude, or leave both empty.");
    const username = String(form.get("username") ?? "").trim().toLowerCase();
    const chosen = agency === "Other" ? other.trim() : agency;
    if (!chosen) return setError("Say which agency the team belongs to.");
    setBusy(true);
    try {
      const r = await api<{ team_id: number; lead: string | null }>("/v1/teams", { method: "POST", json: {
        incident, district: String(form.get("district") ?? ""), name: String(form.get("name") ?? "").trim(), agency: chosen,
        capabilities: caps, has_app: hasApp, radio_channel: hasApp ? null : String(form.get("radio") ?? "") || null,
        lat, lng, max_active: Number(form.get("max") ?? 2) || 2,
        lead: hasApp && username ? { username, name: String(form.get("leadname") ?? "").trim() || undefined,
                                     password: String(form.get("password") ?? "") || undefined } : undefined } });
      onCreated(r.lead ? `Team added. Its lead signs in on the team app as “${r.lead}”.` : "Team added.");
    } catch (e) { setError(say(e)); }
    setBusy(false);
  };

  if (incidents.length === 0) {
    return <p className="p-5 text-body text-ink-2">Start an incident first (the <a className="font-semibold underline underline-offset-4" href="/desk/incidents">Incidents</a> page). A team belongs to one incident and one of its districts.</p>;
  }

  return (
    <form className="grid gap-4 p-4 sm:p-5 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); void submit(new FormData(e.currentTarget)); }}>
      <label className="block text-body"><span className="text-ink-2">Incident</span>
        <select value={incident} onChange={(e) => setIncident(e.target.value)} className="field mt-1">
          {incidents.map((i) => <option key={i.code} value={i.code}>{i.name} ({i.code})</option>)}
        </select></label>
      <label className="block text-body"><span className="text-ink-2">District</span>
        <select name="district" required className="field mt-1" defaultValue="">
          <option value="" disabled>Choose a district</option>
          {districts.map((d) => <option key={d.id} value={d.name}>{d.name}</option>)}
        </select></label>
      <label className="block text-body md:col-span-2"><span className="text-ink-2">Team name</span>
        <input name="name" required minLength={2} placeholder="Fire station 3, Ward 12 volunteers, Medical unit B…" className="field mt-1" /></label>
      <label className="block text-body"><span className="text-ink-2">Agency</span>
        <select value={agency} onChange={(e) => setAgency(e.target.value)} className="field mt-1">
          {(cat?.agencies ?? ["Fire & Rescue", "Other"]).map((a) => <option key={a}>{a}</option>)}
        </select></label>
      {agency === "Other" ? (
        <label className="block text-body"><span className="text-ink-2">Agency name</span>
          <input value={other} onChange={(e) => setOther(e.target.value)} required className="field mt-1" /></label>
      ) : <span aria-hidden className="hidden md:block" />}

      <fieldset className="md:col-span-2">
        <legend className="text-body text-ink-2">What can this team do? <span className="text-ink-3">Pick every one that applies.</span></legend>
        <div className="mt-2 space-y-3">
          {groups.map(([group, items]) => (
            <div key={group}>
              <p className="text-small font-semibold text-ink-3">{group}</p>
              <ul className="mt-1.5 flex flex-wrap gap-2">
                {items.map((c) => {
                  const on = caps.includes(c.key);
                  return (
                    <li key={c.key}>
                      <button type="button" aria-pressed={on} title={c.for} onClick={() => toggle(c.key)}
                              className={`inline-flex h-9 items-center gap-1.5 rounded-full border px-3.5 text-small font-medium transition-colors ${on ? "border-ink bg-ink text-paper" : "border-line bg-paper text-ink-2 hover:border-ink/40 hover:text-ink"}`}>
                        {on ? <Check className="size-3.5" aria-hidden /> : <Plus className="size-3.5 text-ink-3" aria-hidden />}{c.label}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
          {!cat && <p className="text-small text-ink-3">Loading the list…</p>}
        </div>
      </fieldset>

      <label className="flex items-center gap-2 text-body md:col-span-2">
        <input type="checkbox" checked={hasApp} onChange={(e) => setHasApp(e.target.checked)} className="size-4 accent-[#151515]" />
        This team has the team app on a phone (otherwise it is reached by radio or phone calls)
      </label>
      {!hasApp && (
        <label className="block text-body"><span className="text-ink-2">How is it reached?</span>
          <select name="radio" className="field mt-1">{RADIO.map((r) => <option key={r}>{r}</option>)}</select></label>
      )}
      <label className="block text-body"><span className="text-ink-2">Can take at once</span>
        <input name="max" type="number" min={1} max={20} defaultValue={2} className="field tabular mt-1" /></label>
      <label className="block text-body"><span className="text-ink-2">Base latitude <span className="text-ink-3">(optional)</span></span>
        <input name="lat" inputMode="decimal" className="field tabular mt-1" /></label>
      <label className="block text-body"><span className="text-ink-2">Base longitude <span className="text-ink-3">(optional)</span></span>
        <input name="lng" inputMode="decimal" className="field tabular mt-1" /></label>

      {hasApp && (
        <div className="grid gap-3 rounded-2xl bg-wash p-4 md:col-span-2 md:grid-cols-3">
          <p className="text-small text-ink-2 md:col-span-3">Team lead’s sign-in for the team app (optional, you can add it later).</p>
          <label className="block text-body"><span className="text-ink-2">Username</span>
            <input name="username" pattern="[a-z0-9._-]{3,40}" placeholder="station3" className="field mt-1" /></label>
          <label className="block text-body"><span className="text-ink-2">Lead’s name</span>
            <input name="leadname" className="field mt-1" /></label>
          <label className="block text-body"><span className="text-ink-2">Password</span>
            <input name="password" type="password" minLength={8} autoComplete="new-password" className="field mt-1" /></label>
        </div>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button variant="primary" type="submit" disabled={busy}><Plus className="size-4" aria-hidden />{busy ? "Adding…" : "Add the team"}</Button>
      </div>
      {error && <p className="rounded-xl bg-wash px-3 py-2 text-small md:col-span-2">{error}</p>}
    </form>
  );
}
