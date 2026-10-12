"use client";

// Facts with their receipts (PRD F-C13): each value says who produced it (AI · Rule · Human · Partner), whether a
// person checked it (● / ○ / amber ○), and the exact words it came from; hovering lights those words up in the
// report below.

import { useState } from "react";

import { Because, Button, Check, Estimate, MethodChip, type Method } from "@/components/ui";
import { api, type Case, type Prov } from "@/lib/api";

const WORD: Record<string, string> = {
  trapped_on_roof: "on the roof", trapped_inside: "trapped inside", water_entering: "water inside", water_rising: "water rising",
  strong_current: "strong current", buried: "buried", structure_collapsed: "collapse", landslide: "landslide", cut_off: "cut off",
  rescue: "rescue", medicine: "medicine", medical_urgent: "urgent medical", food: "food", drinking_water: "drinking water",
  shelter: "shelter", baby_supplies: "baby milk", elderly: "elderly", infant: "infant", child: "child", pregnant: "pregnant",
  disabled: "disabled", sick: "sick", injured: "injured",
};
export const word = (v: unknown) => (typeof v === "string" ? WORD[v] ?? v.replace(/_/g, " ") : String(v));

function method(p: Prov): Method {
  return (({ ai: "ai", rule: "rule", human: "human", partner: "partner" } as Record<string, Method>)[p.method] ?? "rule");
}

function Receipt({ p, children, onQuote }: { p: Prov; children: React.ReactNode; onQuote: (q: string | null) => void }) {
  const state = p.checked ? "checked" : p.amber ? "amber" : "unchecked";
  return (
    <span className="inline-flex items-center gap-1.5" onMouseEnter={() => onQuote(p.quote ?? null)} onMouseLeave={() => onQuote(null)}>
      <Check state={state} title={p.amber} />
      <span>{children}</span>
      <MethodChip method={method(p)} />
      {p.source === "sheet column" && <span className="text-[10px] text-ink-3">sheet column</span>}
    </span>
  );
}

export function Facts({ c, canEdit, onQuote, onChanged }: {
  c: Case; canEdit: boolean; onQuote: (q: string | null) => void; onChanged: () => void;
}) {
  const prov = c.provenance ?? {};
  const list = (k: string) => ((prov[k] as Prov[] | undefined) ?? []);
  const people = prov.people_count as Prov | undefined;
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (form: FormData) => {
    setError(null);
    try {
      await api(`/v1/cases/${c.id}`, { method: "PATCH", headers: { "If-Match": String(c.version) },
        json: { changes: { people_count: Number(form.get("people")) }, reason: String(form.get("reason") ?? "") } });
      setEditing(false);
      onChanged();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const items = (k: string, values: string[]) => {
    const ps = list(k);
    if (!values.length) return <span className="text-ink-3">none said</span>;
    return (
      <span className="flex flex-col gap-1">
        {values.map((v) => {
          const p = ps.find((x) => x.value === v);
          return p ? <Receipt key={v} p={p} onQuote={onQuote}>{word(v)}</Receipt> : <span key={v}>{word(v)}</span>;
        })}
      </span>
    );
  };

  return (
    <dl className="grid grid-cols-[92px_1fr] gap-x-2 gap-y-2.5 text-sm">
      <dt className="text-ink-3">People</dt>
      <dd>
        {editing ? (
          <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); save(new FormData(e.currentTarget)); }}>
            <input name="people" type="number" min={0} max={5000} defaultValue={c.people_count ?? ""} className="h-8 w-20 rounded-md border border-line px-2 tabular" autoFocus />
            <input name="reason" required minLength={3} placeholder="Why (logged)" className="h-8 flex-1 rounded-md border border-line px-2" />
            <Button size="sm" variant="primary" type="submit">Save</Button>
            <Button size="sm" variant="quiet" type="button" onClick={() => setEditing(false)}>Cancel</Button>
            {error && <span className="w-full text-xs">{error}</span>}
          </form>
        ) : (
          <span className="flex items-center gap-2">
            {people ? <Receipt p={people} onQuote={onQuote}><Estimate value={c.people_count} kind={c.people_count_kind} /></Receipt>
                    : <Estimate value={c.people_count} kind={c.people_count_kind} />}
            {canEdit && <Button size="sm" variant="quiet" onClick={() => setEditing(true)}>Edit</Button>}
          </span>
        )}
      </dd>
      <dt className="text-ink-3">Situation</dt><dd>{items("hazards", c.hazards)}</dd>
      <dt className="text-ink-3">Needs</dt><dd>{items("needs", c.needs)}</dd>
      <dt className="text-ink-3">Vulnerable</dt><dd>{items("vulnerable", c.vulnerable)}</dd>
      <dt className="text-ink-3">Where</dt>
      <dd>
        <span className="flex items-center gap-1.5">
          {c.location_text ?? <span className="text-ink-3">not known yet</span>}
          {c.location_source && <MethodChip method={c.location_source === "human" ? "human" : "rule"} />}
        </span>
        {c.location_method && <Because>{c.location_method}</Because>}
        {(() => {   // P1 #1: a merged report from outside the circle never moves the pin by itself
          const m = (c.attributes?.proposed_move ?? null) as { from: string; metres_away: number; method?: string } | null;
          return m && (
            <p className="mt-1 rounded-md border border-line px-2 py-1 text-xs">
              <b>Proposed move:</b> {m.from}&apos;s report places them {m.metres_away.toLocaleString("en-IN")} m away
              {m.method ? ` (${m.method})` : ""}. The pin stays until a person moves it (Move pin).
            </p>
          );
        })()}
        {list("landmarks").length > 0 && (
          <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
            {list("landmarks").filter((p, i, all) => all.findIndex((q) => JSON.stringify(q.value) === JSON.stringify(p.value)) === i).map((p, i) => {
              const v = p.value as { type: string; name?: string | null; relation?: string };
              return <Receipt key={i} p={p} onQuote={onQuote}>{v.name ? `${v.name} ` : ""}{word(v.type)}{v.relation && v.relation !== "unknown" ? ` (${v.relation})` : ""}</Receipt>;
            })}
          </span>
        )}
      </dd>
    </dl>
  );
}
