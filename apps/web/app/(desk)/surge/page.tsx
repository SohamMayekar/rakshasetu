"use client";

// The surge screen (PRD F-C5): while `make surge` sends synthetic partner reports, this page shows what the
// system is doing about it, once a second, in plain lines (no charts): how fast reports arrive and how fast the
// server says "received", what is still waiting to be read in each lane, what the reports became, and whether
// every promise bar still adds up. The reports are pre-structured, so no language model is called: say so.

import { useCallback, useEffect, useState } from "react";

import { AppShell, Page } from "@/components/shell/AppShell";
import { Button, Card, PageHeader } from "@/components/ui";
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
  ["import", "Sheet imports"], ["surge", "The rush (made up)"], ["backfill", "Re-reading rule-made cases"]];
const n = (v: number) => v.toLocaleString("en-IN");
const ms = (v: number | null) => (v == null ? "–" : `${Math.round(v)} ms`);

export default function SurgePage() {
  const [s, setS] = useState<Surge | null>(null);
  const [bars, setBars] = useState<Promises[]>([]);
  const [integ, setInteg] = useState<Integrity | null>(null);
  const [down, setDown] = useState(false);
  const [checking, setChecking] = useState(false);
  const [details, setDetails] = useState(false);   // response-time percentiles and the per-queue backlog: a click away (m72)
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
    <AppShell>
      <Page>
      <PageHeader title="Under load · the last 60 seconds"
                  sub="Made-up reports arriving fast. Watch that none is lost." />
      {down && <p className="mt-4 rounded-xl bg-ink px-4 py-2 text-body text-paper">Can&apos;t reach the server. Retrying every second.</p>}

      <Card as="dl" className="mt-6 divide-y divide-line px-5 text-body">
        <Row k="Arriving">
          <b className="tabular">{i ? i.per_second.toFixed(1) : "–"}</b> reports a second
          <span className="text-ink-3"> · <span className="tabular">{n(i?.requests ?? 0)}</span> in the last minute
          · <span className="tabular">{n(i?.errors ?? 0)}</span> turned away</span>
        </Row>
        <Row k="What they became">
          <span className="tabular"><b>{n(s?.last_minute.reports ?? 0)}</b> reports read · <b>{n(s?.last_minute.cases ?? 0)}</b> new cases ·{" "}
            <b>{n(s?.last_minute.merges ?? 0)}</b> merged into an existing case</span>
        </Row>
        <Row k="Never lost">
          <ul className="space-y-0.5">
            {bars.map((b) => (
              <li key={b.incident} className="tabular">
                <span className="inline-block w-8 font-medium">{b.incident}</span>
                {n(b.lost.reports)} reports = {n(b.lost.cases)} cases + {n(b.lost.merged)} merged + {n(b.lost.to_check)} to check + {n(b.lost.without_home)} not yet read{" "}
                {b.lost.adds_up ? <span>✓</span> : <span className="rounded-md bg-ink px-1.5 text-paper">doesn&apos;t add up</span>}
                <span className="text-ink-3"> · {n(b.doubled.to_check)} maybe repeats to check · {n(b.doubled.refused)} kept apart</span>
              </li>
            ))}
          </ul>
        </Row>
        <Row k="Integrity">
          {integ ? (integ.problems === 0
            ? <span className="tabular">✓ 0 problems · {n(integ.events_verified)} events verified</span>
            : <span className="rounded-md bg-ink px-1.5 text-paper">{integ.problems} problems: see /v1/integrity</span>) : "–"}{" "}
          <Button size="sm" onClick={check} disabled={checking}>{checking ? "Checking…" : "Check again"}</Button>
        </Row>
        {details && (<>
        <Row k="Time to say “received”">
            <span className="tabular">half within <b>{ms(i?.p50_ms ?? null)}</b> · 95 % within <b>{ms(i?.p95_ms ?? null)}</b> · 99 % within <b>{ms(i?.p99_ms ?? null)}</b></span>
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
        </>)}
        <div className="py-2.5"><Button size="sm" variant="quiet" onClick={() => setDetails(!details)} aria-expanded={details}>
          {details ? "Hide details" : "Show details (response times, what is waiting in each queue)"}</Button></div>
      </Card>
      </Page>
    </AppShell>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-3.5 sm:grid-cols-[11rem_1fr] sm:gap-3">
      <dt className="text-ink-3">{k}</dt>
      <dd>{children}</dd>
    </div>
  );
}
