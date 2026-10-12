"use client";

// The partner log (PRD P1 #13): every partner call, newest first: direction, endpoint, the signature ✓/✗, latency
// and the body's hash; a replayed or forged request shows as what it is ("401 · Stale timestamp: replay rejected").
// And each anchor receipt: a partner anchored our audit head in its own ledger; ✓ if our chain still matches it.

import { useEffect, useState } from "react";

import { Clock } from "@/components/ui";
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
    <main className="mx-auto max-w-5xl px-4 py-6 text-sm">
      <p><a href="/" className="underline underline-offset-2">Incidents</a> · <a href="/audit" className="underline underline-offset-2">Audit</a></p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Partner log</h1>
      <p className="mt-1 text-ink-2">Every call from a partner system, signed or not. Our rules decide what each annotation does: a credibility
        note marks one evidence item, a priority is a suggestion an officer accepts or ignores, an anchor is checked against our chain.</p>
      {error && <p className="mt-3 rounded bg-wash px-3 py-2">{error}</p>}

      {!!data?.anchors.length && (
        <ul className="mt-4 space-y-1">
          {data.anchors.map((a) => (
            <li key={a.annotation_id}>
              {a.matches ? "✓" : <b>✗</b>} Head <span className="tabular">#{a.seq.toLocaleString("en-IN")}</span> anchored by <b>{a.team}</b>
              {" "}(<span className="tabular">{a.receipt}</span>) at <Clock iso={a.at} />
              {!a.matches && <b> · our chain at #{a.seq} no longer matches what they anchored</b>}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 overflow-x-auto">
      <table className="w-full">
        <thead><tr className="border-b border-line text-left text-xs text-ink-3">
          <th className="py-1.5 pr-3">time</th><th className="pr-3">partner</th><th className="hidden pr-3 sm:table-cell">call</th>
          <th className="pr-3">status</th><th className="pr-3">signature</th><th className="hidden pr-3 sm:table-cell">ms</th>
          <th className="hidden sm:table-cell">body sha256</th></tr></thead>
        <tbody>
          {(data?.calls ?? []).map((c) => (
            <tr key={c.id} className="border-b border-line align-top">
              <td className="tabular whitespace-nowrap py-1.5 pr-3"><Clock iso={c.at} /></td>
              <td className="pr-3">{c.team ?? c.partner}<span className="block text-xs text-ink-3">{c.direction === "in" ? "to us" : "from us"}
                <span className="sm:hidden">: {c.method} {c.endpoint}</span></span></td>
              <td className="hidden pr-3 sm:table-cell">{c.method} {c.endpoint}</td>
              <td className="pr-3">{c.status >= 400 ? <b>{c.note ?? c.status}</b> : c.status}</td>
              <td className="pr-3">{c.signature_ok == null ? "–" : c.signature_ok ? "✓" : <b>✗</b>}</td>
              <td className="tabular hidden pr-3 sm:table-cell">{c.latency_ms ?? "–"}</td>
              <td className="tabular hidden text-xs text-ink-3 sm:table-cell">{c.body_sha256 ? `${c.body_sha256.slice(0, 12)}…` : "–"}</td>
            </tr>
          ))}
          {data && !data.calls.length && <tr><td colSpan={7} className="py-6 text-center text-ink-3">No partner calls yet.</td></tr>}
        </tbody>
      </table>
      </div>
    </main>
  );
}
