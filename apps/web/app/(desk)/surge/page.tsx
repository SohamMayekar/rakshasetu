"use client";

// The surge screen (PRD F-C5): while `make surge` sends synthetic partner reports, this page shows what the
// system is doing about it, once a second, in plain lines (no charts): how fast reports arrive and how fast the
// server says "received", what is still waiting to be read in each lane, what the reports became, and whether
// every promise bar still adds up. The reports are pre-structured, so no language model is called: say so.

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui";
import { api, type Me } from "@/lib/api";

type Surge = {
  ingest: { requests: number; accepted: number; errors: number; per_second: number; p50_ms: number | null; p95_ms: number | null; p99_ms: number | null };
  lanes: Record<string, { waiting: number; oldest_s: number }>;
  last_minute: { reports: number; cases: number; merges: number };
};
type Promises = { incident: string; lost: { reports: number; cases: number; merged: number; to_check: number; without_home: number; adds_up: boolean };
                  doubled: { to_check: number; refused: number } };
type Integrity = { problems: number; events_verified: number };

const LANES: [string, string][] = [["live_voice", "Live calls"], ["whatsapp_partner", "WhatsApp and partners"],
  ["import", "Sheet imports"], ["surge", "Surge (synthetic)"], ["backfill", "Re-reading rule-made cases"]];
const n = (v: number) => v.toLocaleString("en-IN");
const ms = (v: number | null) => (v == null ? "–" : `${Math.round(v)} ms`);

export default function SurgePage() {
  const [s, setS] = useState<Surge | null>(null);
  const [bars, setBars] = useState<Promises[]>([]);
  const [integ, setInteg] = useState<Integrity | null>(null);
  const [down, setDown] = useState(false);
  const [checking, setChecking] = useState(false);
  // The integrity check re-walks the whole hash chain (about 0.8 s of the API's CPU at 14,000 events). Run on a
  // timer during a surge it slowed the very ingest it was watching (p95 70 → 810 ms), so it runs on request.
  const check = useCallback(async () => {
    setChecking(true);
    try { setInteg(await api<Integrity>("/v1/integrity")); } catch { setInteg(null); } finally { setChecking(false); }
  }, []);
  useEffect(() => { check(); }, [check]);

  useEffect(() => {
    let tick = 0;
    let codes: string[] | null = null;   // the incidents this person can see
    const poll = async () => {
      try {
        codes ??= (await api<Me>("/v1/me")).incidents.map((i) => i.code);
        setS(await api<Surge>("/v1/metrics/surge"));
        if (tick % 3 === 0) setBars(await Promise.all(codes.map((i) => api<Promises>(`/v1/metrics/promises?incident=${i}`))));
        setDown(false);
      } catch { setDown(true); }
      tick++;
    };
    poll();
    const t = setInterval(poll, 1000);
    return () => clearInterval(t);
  }, []);

  const i = s?.ingest;
  return (
    <main className="mx-auto max-w-3xl px-4 py-6">
      <p className="text-sm"><a href="/" className="underline underline-offset-2">Incidents</a></p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Surge · the last 60 seconds</h1>
      <p className="mt-1 text-sm text-ink-2">
        Synthetic, pre-structured partner reports (<code className="text-xs">make surge</code>): no language model is called, and every
        person and phone number is made up. They queue behind live calls, partners and sheet imports.
      </p>
      {down && <p className="mt-3 rounded bg-ink px-2 py-1 text-sm text-paper">Can&apos;t reach the server. Retrying every second.</p>}

      <dl className="mt-5 divide-y divide-line border-y border-line text-sm">
        <Row k="Arriving">
          <b className="tabular">{i ? i.per_second.toFixed(1) : "–"}</b> reports a second
          <span className="text-ink-3"> · <span className="tabular">{n(i?.requests ?? 0)}</span> in the last minute
          · <span className="tabular">{n(i?.errors ?? 0)}</span> turned away</span>
        </Row>
        <Row k="Time to say “received”">
          <span className="tabular">half within <b>{ms(i?.p50_ms ?? null)}</b> · 95 % within <b>{ms(i?.p95_ms ?? null)}</b> · 99 % within <b>{ms(i?.p99_ms ?? null)}</b></span>
          <span className="block text-ink-3">measured inside the server, from the request arriving to the receipt</span>
        </Row>
        <Row k="Waiting to be read">
          <ul className="space-y-0.5">
            {LANES.map(([lane, label]) => {
              const l = s?.lanes[lane];
              return (
                <li key={lane} className="flex justify-between gap-4">
                  <span>{label}</span>
                  <span className="tabular">{l ? <><b>{n(l.waiting)}</b><span className="text-ink-3"> · oldest {l.oldest_s} s</span></> : <span className="text-ink-3">none</span>}</span>
                </li>
              );
            })}
          </ul>
        </Row>
        <Row k="What they became">
          <span className="tabular"><b>{n(s?.last_minute.reports ?? 0)}</b> reports read · <b>{n(s?.last_minute.cases ?? 0)}</b> new cases ·{" "}
            <b>{n(s?.last_minute.merges ?? 0)}</b> merged into an existing case</span>
          <span className="block text-ink-3">in the last minute, all incidents</span>
        </Row>
        <Row k="Never lost">
          <ul className="space-y-0.5">
            {bars.map((b) => (
              <li key={b.incident} className="tabular">
                <span className="inline-block w-8 font-medium">{b.incident}</span>
                {n(b.lost.reports)} reports = {n(b.lost.cases)} cases + {n(b.lost.merged)} merged + {n(b.lost.to_check)} to check + {n(b.lost.without_home)} without a home{" "}
                {b.lost.adds_up ? <span>✓</span> : <span className="rounded bg-ink px-1.5 text-paper">doesn&apos;t add up</span>}
                <span className="text-ink-3"> · {n(b.doubled.to_check)} possible duplicates to check · {n(b.doubled.refused)} kept apart</span>
              </li>
            ))}
          </ul>
          <span className="block text-ink-3">“without a home” here is the backlog: stored with a receipt, not yet read. It returns to 0 as the backlog clears.</span>
        </Row>
        <Row k="Integrity">
          {integ ? (integ.problems === 0
            ? <span className="tabular">✓ 0 problems · {n(integ.events_verified)} events verified</span>
            : <span className="rounded bg-ink px-1.5 text-paper">{integ.problems} problems: see /v1/integrity</span>) : "–"}{" "}
          <Button size="sm" onClick={check} disabled={checking}>{checking ? "Checking…" : "Check again"}</Button>
          <span className="block text-ink-3">every invariant, and the whole hash chain re-walked: run it after the surge</span>
        </Row>
      </dl>
    </main>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-2.5 sm:grid-cols-[11rem_1fr] sm:gap-3">
      <dt className="text-ink-3">{k}</dt>
      <dd>{children}</dd>
    </div>
  );
}
