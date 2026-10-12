"use client";

// Sheets: the volunteer spreadsheets added to this incident and what became of every row (new families, the same
// family again, rows to check, rows that could not be read). Adding or opening a sheet happens on the desk.

import { FileSpreadsheet, Plus } from "lucide-react";
import { use, useEffect, useState } from "react";

import { IncidentPage, useMe } from "@/components/desk/IncidentPage";
import { Card, Empty, useNow, ago } from "@/components/ui";
import { api } from "@/lib/api";

type Sheet = { id: number; file_name: string; file_kind: string; rows_total: number; rows_done: number; new_cases: number;
               merged: number; to_check: number; dropped: number; phones_damaged: number; warnings: string[];
               status: "uploaded" | "mapped" | "running" | "done" | "failed"; created_at: string; finished_at: string | null };

const STATUS: Record<Sheet["status"], string> = {
  uploaded: "Columns to confirm", mapped: "Waiting to start", running: "Adding rows…", done: "Done", failed: "Could not finish",
};
const n = (v: number) => v.toLocaleString("en-IN");

function Num({ value, label }: { value: number; label: string }) {
  return (
    <span className="min-w-0">
      <span className="tabular block text-body font-semibold">{n(value)}</span>
      <span className="block text-small text-ink-3">{label}</span>
    </span>
  );
}

export default function Sheets({ params }: { params: Promise<{ incident: string }> }) {
  const { incident } = use(params);
  const me = useMe();
  const now = useNow(30_000);
  const [sheets, setSheets] = useState<Sheet[] | null>(null);

  useEffect(() => {
    const load = () => api<Sheet[]>(`/v1/imports?incident=${encodeURIComponent(incident)}`).then(setSheets).catch(() => setSheets([]));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [incident]);

  return (
    <IncidentPage me={me} code={incident} title="Sheets" sub="volunteer spreadsheets and what became of each row"
                  aside={<a href={`/desk/${incident}?import=new`} className="inline-flex h-10 items-center gap-2 rounded-full bg-ink px-4 text-body font-medium text-paper active:scale-[0.98]">
                    <Plus className="size-4" aria-hidden />Add a sheet</a>}>
      <Card className="overflow-hidden">
        {!sheets ? <Empty>Loading…</Empty> : sheets.length === 0 ? <Empty>No sheets yet. Add a volunteer&rsquo;s Excel or CSV file.</Empty> : (
          <ul className="divide-y divide-line">
            {sheets.map((s) => (
              <li key={s.id}>
                <a href={`/desk/${incident}?import=${s.id}`}
                   className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-3 px-4 py-3.5 transition-colors hover:bg-wash md:grid-cols-[auto_minmax(0,1fr)_repeat(4,6.5rem)_9rem]">
                  <FileSpreadsheet className="size-5 text-ink-3" strokeWidth={1.8} aria-hidden />
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{s.file_name}</span>
                    <span className="tabular block text-small text-ink-3">
                      {n(s.rows_total)} rows · added {ago(s.created_at, now)}
                    </span>
                  </span>
                  <span className="col-span-2 grid grid-cols-4 gap-3 md:contents">
                    <Num value={s.new_cases} label="new families" />
                    <Num value={s.merged} label="already known" />
                    <Num value={s.to_check} label="to check" />
                    <Num value={s.dropped} label="not readable" />
                  </span>
                  <span className={`col-span-2 text-small md:col-span-1 md:text-right ${s.status === "done" ? "text-ink-2" : "font-medium text-ink"}`}>
                    {s.status === "running" ? `Adding rows… ${n(s.rows_done)} of ${n(s.rows_total)}` : STATUS[s.status]}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </IncidentPage>
  );
}
