"use client";

// The partner log (PRD P1 #13): every partner call, newest first: direction, endpoint, the signature ✓/✗, latency
// and the body's hash; a replayed or forged request shows as what it is ("401 · Stale timestamp: replay rejected").
// And each anchor receipt: a partner anchored our audit head in its own ledger; ✓ if our chain still matches it.

import { Handshake } from "lucide-react";
import { useEffect, useState } from "react";

import { AppShell, Page } from "@/components/shell/AppShell";
import { Card, Clock, IconWell, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

type Call = { id: number; at: string; partner: string | null; team: string | null; direction: "in" | "out"; method: string;
              endpoint: string; status: number; signature_ok: boolean | null; latency_ms: number | null; body_sha256: string | null;
              note: string | null };
type Anchor = { annotation_id: number; team: string; seq: number; receipt: string; at: string; matches: boolean };

export default function PartnerLog() {
  const [data, setData] = useState<{ calls: Call[]; anchors: Anchor[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const load = () => api<{ calls: Call[]; anchors: Anchor[] }>("/v1/partners/log").then((d) => { setData(d); setError(null); })
      .catch((e) => setError(String(e instanceof Error ? e.message : e)));
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, []);

  return (
    <AppShell>
      <Page wide>
        <PageHeader title="A partner system"
                    sub="Another team's system can send us notes about a case. This one is our own, simulated. Every call, both ways:" />
        {error && <p className="mt-4 rounded-xl bg-paper px-4 py-2 text-sm">{error}</p>}

        {!!data?.anchors.length && (
          <Card className="mt-5 space-y-2 px-5 py-4 text-sm">
            {data.anchors.map((a) => (
              <p key={a.annotation_id} className="flex items-center gap-2.5"><IconWell icon={Handshake} size="sm" />
                <span>{a.matches ? "✓" : <b>✗</b>} <b>{a.team}</b> keeps a copy of our history up to entry <span className="tabular">#{a.seq.toLocaleString("en-IN")}</span>
                  {" "}(<span className="tabular">{a.receipt}</span>, <Clock iso={a.at} />){a.matches ? ": ours still matches it" : <b>: ours no longer matches their copy</b>}</span>
              </p>
            ))}
          </Card>
        )}

        <Card className="mt-5 overflow-x-auto text-sm">
          <table className="w-full">
            <thead><tr className="border-b border-line text-left text-xs text-ink-3">
              <th className="py-3 pl-5 pr-3 font-medium">time</th><th className="pr-3 font-medium">who</th><th className="hidden pr-3 font-medium sm:table-cell">call</th>
              <th className="pr-3 font-medium">answer</th><th className="pr-3 font-medium">signed</th><th className="hidden pr-3 font-medium sm:table-cell">ms</th>
              <th className="hidden pr-5 font-medium sm:table-cell">fingerprint</th></tr></thead>
            <tbody>
              {(data?.calls ?? []).map((c) => (
                <tr key={c.id} className="border-b border-line align-top last:border-b-0 hover:bg-wash/60">
                  <td className="tabular whitespace-nowrap py-2.5 pl-5 pr-3"><Clock iso={c.at} /></td>
                  <td className="py-2.5 pr-3">{c.team ?? c.partner}<span className="block text-xs text-ink-3">{c.direction === "in" ? "to us" : "from us"}
                    <span className="sm:hidden">: {c.method} {c.endpoint}</span></span></td>
                  <td className="hidden py-2.5 pr-3 sm:table-cell">{c.method} {c.endpoint}</td>
                  <td className="py-2.5 pr-3">{c.status >= 400 ? <b>{c.note ?? c.status}</b> : c.status}</td>
                  <td className="py-2.5 pr-3">{c.direction === "out" ? <span className="whitespace-nowrap text-ink-2">signed by us</span>
                    : c.signature_ok == null ? "–" : c.signature_ok ? "✓" : <b>✗</b>}</td>
                  <td className="tabular hidden py-2.5 pr-3 sm:table-cell">{c.latency_ms ?? "–"}</td>
                  <td className="tabular hidden py-2.5 pr-5 text-xs text-ink-3 sm:table-cell">{c.body_sha256 ? `${c.body_sha256.slice(0, 12)}…` : "–"}</td>
                </tr>
              ))}
              {data && !data.calls.length && <tr><td colSpan={7} className="py-10 text-center text-ink-3">No partner calls yet.</td></tr>}
            </tbody>
          </table>
        </Card>
      </Page>
    </AppShell>
  );
}
