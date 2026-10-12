"use client";

// The Audit screen (PRD F-C8): the hash-chained event log, newest first, and "Verify chain", which recomputes
// every hash and reports "✓ 1,284 events verified" or the first broken link. Tamper-evident (that is the claim):
// the app can't edit history; a database superuser could, which is why a partner can countersign the head.

import { Handshake, ShieldAlert, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { AppShell, Page } from "@/components/shell/AppShell";
import { Button, Card, IconWell, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

type Ev = { seq: number; at: string; actor: { type: string; id: string | null; role: string | null }; action: string;
            entity: { type: string; id: string | null }; case_id: number | null; data: Record<string, unknown>; reason: string | null; hash: string };
type Verify = { ok: boolean; count: number; broken_at: number | null; problem: string | null };

export default function Audit() {
  const [events, setEvents] = useState<Ev[] | null>(null);
  const [verify, setVerify] = useState<Verify | null>(null);
  const [busy, setBusy] = useState(false);
  const [caseId, setCaseId] = useState<string | null>(null);

  useEffect(() => {
    const c = new URLSearchParams(location.search).get("case");
    setCaseId(c);
    (async () => {
      const head = await api<{ seq: number }>("/v1/audit/head");
      const q = c ? `case_id=${c}&limit=500` : `after_seq=${Math.max(0, head.seq - 300)}&limit=300`;
      setEvents((await api<Ev[]>(`/v1/audit?${q}`)).reverse());
    })().catch(() => setEvents([]));
  }, []);

  const [anchors, setAnchors] = useState<{ annotation_id: number; team: string; seq: number; matches: boolean }[]>([]);
  const run = async () => {
    setBusy(true);
    try {
      setVerify(await api<Verify>("/v1/audit/verify"));
      setAnchors((await api<{ anchors: typeof anchors }>("/v1/partners/log?limit=1").catch(() => ({ anchors: [] }))).anchors);
    } finally { setBusy(false); }
  };

  return (
    <AppShell>
      <Page wide>
        <PageHeader title={<>Audit{caseId ? <span className="text-ink-3"> · case #{caseId}</span> : ""}</>}
                    sub="Every change is one event, hash-chained to the one before. Tamper-evident: an edit to history breaks the chain at that row."
                    aside={<Button variant="primary" onClick={run} disabled={busy}><ShieldCheck className="size-4" aria-hidden />{busy ? "Verifying…" : "Verify chain"}</Button>} />
        {(verify || anchors.length > 0) && (
          <Card className="mt-5 flex flex-col gap-2 px-5 py-4 text-sm">
            {verify && (verify.ok
              ? <p className="flex items-center gap-2.5"><IconWell icon={ShieldCheck} size="sm" /><span>✓ <b className="tabular">{verify.count.toLocaleString("en-IN")}</b> events verified</span></p>
              : <p className="flex items-center gap-2.5"><IconWell icon={ShieldAlert} size="sm" tone="ink" /><span className="rounded-md bg-ink px-2 py-0.5 text-paper">Broken at seq {verify.broken_at}: {verify.problem}</span></p>)}
            {anchors.map((a) => (
              <p key={a.annotation_id} className="flex items-center gap-2.5"><IconWell icon={Handshake} size="sm" />
                <span>{a.matches ? "✓" : <b>✗</b>} Head <span className="tabular">#{a.seq.toLocaleString("en-IN")}</span> anchored by {a.team}
                  {a.matches ? ": our chain still matches it" : <b>: our chain no longer matches what they anchored</b>}</span></p>
            ))}
          </Card>
        )}
        <Card className="mt-5 overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-xs text-ink-3">
              <th className="py-3 pl-5 pr-3 font-medium">seq</th><th className="pr-3 font-medium">time</th><th className="pr-3 font-medium">who</th>
              <th className="pr-3 font-medium">what</th><th className="pr-3 font-medium">reason</th><th className="pr-5 font-medium">hash</th></tr></thead>
            <tbody>
              {(events ?? []).map((e) => (
                <tr key={e.seq} className="border-b border-line align-top last:border-b-0 hover:bg-wash/60">
                  <td className="tabular py-2 pl-5 pr-3 text-ink-3">{e.seq}</td>
                  <td className="tabular whitespace-nowrap py-2 pr-3">{new Date(e.at).toLocaleTimeString("en-IN", { hour12: false })}</td>
                  <td className="py-2 pr-3">{e.actor.type === "user" ? `${e.actor.role}` : e.actor.type}</td>
                  <td className="py-2 pr-3"><span className="font-medium">{e.action}</span> <span className="text-ink-3">{e.entity.type} {e.entity.id}</span></td>
                  <td className="py-2 pr-3 text-ink-2">{e.reason}</td>
                  <td className="tabular py-2 pr-5 text-xs text-ink-3">{e.hash.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </Page>
    </AppShell>
  );
}
