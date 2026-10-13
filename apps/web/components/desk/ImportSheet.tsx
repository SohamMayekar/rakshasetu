"use client";

// The spreadsheet side sheet (PRD F-D3), over the live desk: drop a volunteer's CSV/XLSX, see how the first rows
// will be read (with every flag, e.g. "phone damaged by Excel"), confirm the column mapping in one click, watch it
// import row by row, then read the summary and any row's reason. The desk keeps working underneath.

import { useCallback, useEffect, useState } from "react";

import { Button, Chip } from "@/components/ui";
import { api, type Me } from "@/lib/api";

import { IncidentSelect } from "./IncidentSelect";

type Imp = {
  id: number; file_name: string; file_kind: string; status: string; headers: string[]; proposed: Record<string, string>;
  mapping: Record<string, string> | null; preview: { row: number; cells: string[]; reads_as: Record<string, unknown>; flags: string[] }[];
  rows_total: number; rows_done: number; new_cases: number; merged: number; to_check: number; history: number; already: number;
  dropped: number; pending: number; rules_read: number; ai_asked: number; phones_damaged: number; warnings: string[];
  summary: string | null; created_at: string;
};
type Row = { row_number: number; outcome: string; read_by: string | null; reason: string; flags: string[];
             case_id: number | null; public_id: string | null; priority: string | null; status: string | null; owned: boolean };

const FIELDS = ["name", "phone", "headcount", "location", "village", "district", "needs", "notes", "status", "time", "ignore"];
const OUTCOMES: [string, string][] = [["waiting", "waiting for a team"], ["new", "new"], ["merged", "merged"], ["to_check", "to check"],
  ["history", "closed history"], ["already", "already imported"], ["dropped", "dropped"], ["pending", "still processing"]];

// A row's flag codes in plain words (the glossary, docs/SIMPLIFY_PLAN.md).
const flagWord = (f: string) => ({ needs_location: "where exactly?", old_report: "old report", sheet_says_done: "the sheet says done" } as Record<string, string>)[f]
  ?? f.replace(/_/g, " ");

export function ImportSheet({ incident: initial, incidents, openId, initialFilter, onOpenCase, onClose }: {
  incident: string; incidents: Me["incidents"]; openId: number | null; initialFilter?: string; onOpenCase: (caseId: number) => void; onClose: () => void;
}) {
  const [incident, setIncident] = useState(initial);
  const [imp, setImp] = useState<Imp | null>(null);
  const [recent, setRecent] = useState<Imp[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [rows, setRows] = useState<Row[] | null>(null);
  const [filter, setFilter] = useState(initialFilter ?? "to_check");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback((id: number) => api<Imp>(`/v1/imports/${id}`).then((x) => { setImp(x); setMapping(x.mapping ?? x.proposed); return x; }), []);

  useEffect(() => {
    if (openId != null) load(openId).catch((e) => setError(String(e.message)));
    else api<Imp[]>("/v1/imports").then(setRecent).catch(() => {});
  }, [openId, load]);
  useEffect(() => { if (initialFilter) setFilter(initialFilter); }, [initialFilter]);

  useEffect(() => {   // live progress while the job runs (the desk stays usable: this is a 1 s poll of one row)
    if (!imp || !["mapped", "running"].includes(imp.status)) return;
    const t = setInterval(() => load(imp.id), 1000);
    return () => clearInterval(t);
  }, [imp, load]);

  useEffect(() => {
    if (!imp || imp.status !== "done") return;
    api<Row[]>(`/v1/imports/${imp.id}/rows?limit=5000`).then(setRows).catch(() => {});
  }, [imp?.id, imp?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file: File) => {
    if (!incident) { setError("Start an incident first (the Incidents page), then add the sheet."); return; }
    setBusy(true); setError(null);
    const form = new FormData();
    form.set("file", file); form.set("incident", incident);
    try {
      const r = await fetch("/v1/imports", { method: "POST", body: form });
      const body = await r.json();
      if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
      setImp(body); setMapping(body.proposed);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };

  const confirm = async () => {
    setBusy(true); setError(null);
    try { setImp(await api<Imp>(`/v1/imports/${imp!.id}/mapping`, { method: "POST", json: { mapping } })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };

  const shown = rows?.filter((r) => filter === "waiting" ? r.outcome === "new" && !r.owned && r.status !== "closed" : r.outcome === filter) ?? [];
  const count = (k: string) => rows?.filter((r) => k === "waiting" ? r.outcome === "new" && !r.owned && r.status !== "closed" : r.outcome === k).length ?? 0;

  return (
    <aside className="panel-in fixed inset-0 z-40 flex flex-col overflow-hidden bg-paper md:static md:h-full md:w-[500px] md:shrink-0 md:rounded-card md:border md:border-line/80 md:shadow-[var(--shadow-card)]" aria-label="Import a sheet">
      <div className="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 className="text-lg font-semibold tracking-tight">{imp ? imp.file_name : "Import a volunteer sheet"}</h2>
        <Button variant="quiet" size="sm" onClick={onClose}>Close</Button>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-4 text-body">
        {!imp && (
          <>
            <div className="mb-3"><IncidentSelect incidents={incidents} value={incident} onChange={setIncident} /></div>
            <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-ink-3 px-4 py-10 text-center hover:bg-wash"
                   onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) upload(f); }}>
              <span className="font-medium">{busy ? "Reading…" : "Drop a CSV or XLSX here, or choose a file"}</span>
              <span className="text-small text-ink-3">Excel or CSV, up to 5,000 rows.</span>
              <input type="file" accept=".csv,.xlsx" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); }} />
            </label>
            {recent.length > 0 && (
              <ul className="mt-6 divide-y divide-line">
                {recent.map((r) => (
                  <li key={r.id}><button className="w-full py-2 text-left hover:bg-wash" onClick={() => load(r.id)}>
                    <span className="font-medium">{r.file_name}</span> <span className="text-ink-3">· {r.status}</span>
                    {r.summary && <span className="block text-small text-ink-2">{r.summary}</span>}
                  </button></li>
                ))}
              </ul>
            )}
          </>
        )}

        {imp && imp.status === "uploaded" && (
          <>
            <p className="text-ink-2"><span className="tabular">{imp.rows_total}</span> rows. Check how each column will be read, then import.</p>
            {imp.warnings.map((w) => <p key={w} className="mt-2 rounded-md bg-wash px-2 py-1">{w}</p>)}
            <table className="mt-3 w-full">
              <tbody>
                {imp.headers.map((h) => (
                  <tr key={h} className="border-b border-line">
                    <td className="py-1.5 pr-2 font-medium">{h}</td>
                    <td className="py-1.5">
                      <select value={mapping[h] === "unknown" ? "ignore" : mapping[h]} onChange={(e) => setMapping({ ...mapping, [h]: e.target.value })}
                              className="field-compact">
                        {FIELDS.map((f) => <option key={f} value={f}>{f}</option>)}
                      </select>
                      {imp.proposed[h] === "unknown" && <span className="ml-2 text-small text-ink-3">not used</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h3 className="mt-5 text-small font-semibold text-ink-2">How the first rows read</h3>
            <ol className="mt-1 space-y-1.5">
              {imp.preview.map((p) => {
                const r = p.reads_as;
                return (
                  <li key={p.row} className="rounded-md bg-wash px-2 py-1.5 text-small">
                    <span className="tabular text-ink-3">row {p.row} · </span>
                    {[r.name, r.headcount != null && `${r.headcount_kind === "estimated" ? "~" : ""}${r.headcount} people`, r.village, r.phone].filter(Boolean).join(" · ")}
                    {p.flags.map((f) => <Chip key={f} tone="attention">{flagWord(f)}</Chip>)}
                  </li>
                );
              })}
            </ol>
            <div className="mt-5"><Button variant="primary" disabled={busy} onClick={confirm}>Confirm mapping and import</Button></div>
          </>
        )}

        {imp && ["mapped", "running"].includes(imp.status) && (
          <div>
            <p className="font-medium">Importing row by row…</p>
            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-wash">
              <div className="h-full bg-ink transition-[width] duration-300" style={{ width: `${imp.rows_total ? (100 * imp.rows_done) / imp.rows_total : 0}%` }} />
            </div>
            <p className="mt-2 tabular text-ink-2">{imp.rows_done} of {imp.rows_total} · {imp.new_cases} new · {imp.merged} merged · {imp.to_check} to check · rules read {imp.rules_read}, AI asked about {imp.ai_asked}</p>
          </div>
        )}

        {imp?.status === "done" && (
          <>
            <p className="text-body font-medium leading-snug">{imp.summary}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {OUTCOMES.filter(([k]) => count(k) > 0).map(([k, label]) => (
                <button key={k} onClick={() => setFilter(k)}
                        className={`rounded-full px-2.5 py-1 text-small ${filter === k ? "bg-ink text-paper" : "border border-line text-ink-2 hover:bg-wash"}`}>
                  <span className="tabular">{count(k)}</span> {label}
                </button>
              ))}
            </div>
            <ol className="mt-3 divide-y divide-line">
              {shown.map((r) => (
                <li key={r.row_number} className="flex items-start justify-between gap-3 py-2">
                  <span className="min-w-0">
                    <span className="tabular text-small text-ink-3">row {r.row_number}</span>
                    <span className="block text-body">{r.reason}</span>
                    {r.flags.length > 0 && <span className="text-small text-ink-2">{r.flags.map(flagWord).join(" · ")}</span>}
                  </span>
                  {r.case_id && <Button size="sm" className="shrink-0" onClick={() => onOpenCase(r.case_id!)}>{r.public_id}</Button>}
                </li>
              ))}
            </ol>
          </>
        )}
        {error && <p className="mt-3 rounded-md bg-wash px-2 py-1 text-small">{error}</p>}
      </div>
    </aside>
  );
}
