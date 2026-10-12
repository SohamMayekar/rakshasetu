"use client";

// The desk (PRD F-C2): queue on the left, map in the centre, the case drawer on the right. Live updates arrive
// in 1-second frames; the cases they name are re-read from the API (scoped), so the screen shows only what
// this user may see, and it is never more than a second behind the database.

import { use, useCallback, useEffect, useMemo, useState } from "react";

import { CaseList, sortForDesk } from "@/components/desk/CaseList";
import { CaseMap } from "@/components/desk/CaseMap";
import { Drawer } from "@/components/desk/Drawer";
import { Header } from "@/components/desk/Header";
import { api, ApiError, type Case, listCases, type Me } from "@/lib/api";
import { type Envelope, useLive } from "@/lib/live";

const CLOSED = new Set(["merged", "cancelled"]);

function caseIds(events: Envelope[]): number[] {
  const ids = new Set<number>();
  for (const e of events) {
    for (const k of ["case_id", "target_case_id", "source_case_id", "candidate_case_id"]) {
      const v = e.data?.[k];
      if (typeof v === "number") ids.add(v);
    }
  }
  return [...ids];
}

export default function Desk({ params }: { params: Promise<{ incident: string }> }) {
  const { incident } = use(params);
  const [me, setMe] = useState<Me | null>(null);
  const [cases, setCases] = useState<Map<number, Case>>(new Map());
  const [since, setSince] = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    api<Me>("/v1/me").then(setMe).catch((e) => { if (e instanceof ApiError && e.status === 401) location.href = "/login"; });
    listCases({ incident }).then(({ cases, seq }) => {
      setCases(new Map(cases.map((c) => [c.id, c])));
      setSince(seq);
      const want = new URLSearchParams(location.search).get("case");   // deep link: /desk/BR?case=BR-214
      const hit = want ? cases.find((c) => c.public_id === want || String(c.id) === want) : undefined;
      if (hit) setSelected(hit.id);
    })
      .catch((e) => { if (e instanceof ApiError && e.status === 401) location.href = "/login"; });
  }, [incident]);

  const onFrame = useCallback(async (events: Envelope[]) => {
    const ids = caseIds(events);
    if (!ids.length) return;
    const { cases: fresh } = await listCases({ ids });
    setCases((prev) => {
      const next = new Map(prev);
      for (const id of ids) next.delete(id);          // gone from scope (or merged away) unless re-read below
      for (const c of fresh) if (c.incident_code === incident) next.set(c.id, c);
      return next;
    });
  }, [incident]);
  const live = useLive(incident, since, onFrame);

  const open = useMemo(() => [...cases.values()].filter((c) => !CLOSED.has(c.status) && c.status !== "closed").sort(sortForDesk), [cases]);
  const current = selected != null ? cases.get(selected) ?? null : null;

  return (
    <div className="flex h-screen flex-col">
      <Header me={me} incident={incident} live={live} />
      <div className="flex min-h-0 flex-1">
        <nav className="w-full shrink-0 overflow-y-auto border-r border-line md:w-[380px]" aria-label="Cases">
          <p className="px-4 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">
            Cases <span className="tabular">{open.length}</span>
          </p>
          <CaseList cases={open} selected={selected} onSelect={setSelected} />
        </nav>
        <main className="relative hidden min-w-0 flex-1 md:block">
          <CaseMap cases={open} selected={selected} onSelect={setSelected} />
        </main>
        {current && <Drawer c={current} onClose={() => setSelected(null)} />}
      </div>
    </div>
  );
}
