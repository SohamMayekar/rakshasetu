"use client";

// The drawer's "Assignment" (PRD F-C2, F-C4, F-S1): who owns this case and when they must next be heard from,
// or, with no owner, the three best teams and why. Officers act here; the system never assigns on its own.

import { useEffect, useState } from "react";

import { Because, Button, Chip, Ring } from "@/components/ui";
import { api, type Assignment, type Case, type Dispatch, type Escalation } from "@/lib/api";

const CHANNELS = ["VHF", "HAM", "satellite", "phone"];
const PHASE: Record<string, string> = { offered: "assigned, not acknowledged yet", acknowledged: "acknowledged", reached: "on scene" };

function windowMs(a: Assignment) {
  const from = Math.max(new Date(a.created_at).getTime(), a.last_contact_at ? new Date(a.last_contact_at).getTime() : 0);
  return Math.max(new Date(a.next_contact_due).getTime() - from, 60_000);
}

function Radio({ a, onDone }: { a: Assignment; onDone: () => void }) {
  const [channel, setChannel] = useState(a.radio_channel && CHANNELS.includes(a.radio_channel) ? a.radio_channel : "VHF");
  const [eta, setEta] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const send = async () => {
    try { await api(`/v1/teams/${a.team_id}/contact`, { method: "POST", json: { channel, new_eta: eta } }); onDone(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  return (
    <div className="mt-2 space-y-2 rounded-lg border border-line p-3">
      <p className="text-sm">Heard from <b>{a.team}</b> on</p>
      <div className="flex flex-wrap gap-1.5">
        {CHANNELS.map((c) => <button key={c} onClick={() => setChannel(c)} className={`rounded-full px-2.5 py-1 text-xs ${channel === c ? "bg-ink text-paper" : "border border-line"}`}>{c}</button>)}
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-ink-2">New ETA (optional):
        {[15, 30, 60].map((m) => <button key={m} onClick={() => setEta(eta === m ? null : m)} className={`rounded-full px-2.5 py-1 ${eta === m ? "bg-ink text-paper" : "border border-line"}`}>{m} min</button>)}
      </div>
      <p className="text-xs text-ink-3">One log refreshes every case this team holds.</p>
      <div className="flex gap-2"><Button size="sm" variant="primary" onClick={send}>Log contact</Button></div>
      {error && <p className="text-xs">{error}</p>}
    </div>
  );
}

export function AssignmentPanel({ c, assignment, escalation, can, onChanged }: {
  c: Case; assignment: Assignment | null; escalation?: Escalation; can: (a: string) => boolean; onChanged: () => void;
}) {
  const [dispatch, setDispatch] = useState<Dispatch | null>(null);
  const [mode, setMode] = useState<"radio" | "release" | "reassign" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMode(null); setError(null);
    if (!assignment || assignment.state === "overdue")
      api<Dispatch>(`/v1/cases/${c.id}/dispatch-suggestions`).then(setDispatch).catch(() => setDispatch(null));
  }, [c.id, c.version, assignment?.id, assignment?.state]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); setMode(null); onChanged(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  if (assignment) {
    const a = assignment;
    return (
      <div className="space-y-2 text-sm">
        <p>Assigned to <b>{a.team}</b>{!a.has_app && <span className="text-ink-3"> · radio only ({a.radio_channel})</span>}</p>
        <p className="text-ink-2">{PHASE[a.phase]}{a.eta_minutes ? ` · ETA ${a.eta_minutes} min` : ""}{a.assigned_by ? ` · by ${a.assigned_by}` : ""}</p>
        <Ring due={a.next_contact_due} windowMs={windowMs(a)} overdue={a.state === "overdue"} demo={a.demo_clock}
              label={a.has_app ? "check-in due" : "radio check due"} />
        {a.state === "overdue" && <Because>no contact since {a.last_contact_at ? new Date(a.last_contact_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false }) : "it was assigned"}. The case stays with the team until you act.</Because>}
        {a.last_seen_at && <p className="text-xs text-ink-3">App last seen {new Date(a.last_seen_at).toLocaleTimeString("en-IN", { hour12: false })} (display only: it never extends the check-in)</p>}
        <div className="flex flex-wrap gap-2 pt-1">
          {can("team.radio_contact") && <Button size="sm" variant={a.state === "overdue" ? "primary" : "secondary"} onClick={() => setMode(mode === "radio" ? null : "radio")}>Heard on radio</Button>}
          {can("assignment.team_action") && a.phase === "offered" && (
            <Button size="sm" onClick={() => run(() => api(`/v1/assignments/${a.id}/acknowledge`, { method: "POST", json: { eta_minutes: 30, channel: a.radio_channel && CHANNELS.includes(a.radio_channel) ? a.radio_channel : "phone" } }))}>
              Acknowledged on radio · ETA 30
            </Button>
          )}
          {a.state === "overdue" && escalation && can("assignment.create") && (
            <Button size="sm" onClick={() => setMode(mode === "reassign" ? null : "reassign")}>Reassign</Button>
          )}
          {can("assignment.team_action") && <Button size="sm" variant="quiet" onClick={() => setMode(mode === "release" ? null : "release")}>Release</Button>}
        </div>
        {mode === "reassign" && escalation && dispatch && (
          <ol className="space-y-1.5">
            {dispatch.suggestions.map((t) => (
              <li key={t.team_id} className="flex items-start justify-between gap-3 rounded-lg border border-line px-3 py-2">
                <span className="min-w-0"><span className="font-medium">{t.name}</span><span className="block text-xs text-ink-2">{t.line}</span></span>
                <Button size="sm" className="shrink-0" onClick={() => run(() => api(`/v1/escalations/${escalation.id}/reassign`, { method: "POST", json: { case: c.public_id, team_id: t.team_id } }))}>Reassign here</Button>
              </li>
            ))}
            <li className="text-xs text-ink-3">{a.team} will show &ldquo;stand-down not acknowledged&rdquo; until it is next heard from.</li>
          </ol>
        )}
        {mode === "radio" && <Radio a={a} onDone={() => { setMode(null); onChanged(); }} />}
        {mode === "release" && (
          <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); const reason = String(new FormData(e.currentTarget).get("reason"));
            run(() => api(`/v1/assignments/${a.id}/release`, { method: "POST", json: { reason, channel: "phone" } })); }}>
            <input name="reason" required minLength={3} autoFocus placeholder="Why release? (logged)" className="h-8 min-w-0 flex-1 rounded-md border border-line px-2" />
            <Button size="sm" variant="primary" type="submit">Release</Button>
          </form>
        )}
        {error && <p className="rounded-md bg-wash px-2 py-1 text-xs">{error}</p>}
      </div>
    );
  }

  if (!dispatch) return <p className="text-sm text-ink-2">No team yet.</p>;
  const assign = (teamId: number, rank?: number) => run(() => api("/v1/assignments", { method: "POST", json: { case: c.public_id, team_id: teamId, suggested_rank: rank } }));
  return (
    <div className="space-y-2 text-sm">
      <p className="text-ink-2">No team yet. Suggested (nearest suitable unit, as a dispatcher would rank them):</p>
      <ol className="space-y-1.5">
        {dispatch.suggestions.map((t) => (
          <li key={t.team_id} className="flex items-start justify-between gap-3 rounded-lg border border-line px-3 py-2">
            <span className="min-w-0"><span className="font-medium">{t.name}</span><span className="block text-xs text-ink-2">{t.line}</span></span>
            {can("assignment.create") && <Button size="sm" variant={t.rank === 1 ? "primary" : "secondary"} className="shrink-0" onClick={() => assign(t.team_id, t.rank)}>Assign</Button>}
          </li>
        ))}
      </ol>
      {(dispatch.more.length > 0 || dispatch.greyed.length > 0) && (
        <details className="text-xs text-ink-2">
          <summary className="cursor-pointer select-none">Other teams ({dispatch.more.length} available · {dispatch.greyed.length} not)</summary>
          <ul className="mt-1 space-y-1">
            {dispatch.more.map((t) => (
              <li key={t.team_id} className="flex items-center justify-between gap-2"><span>{t.name} · {t.line}</span>
                {can("assignment.create") && <Button size="sm" variant="quiet" onClick={() => assign(t.team_id)}>Assign</Button>}</li>
            ))}
            {dispatch.greyed.map((g) => <li key={g.team_id} className="stale">{g.name} · <Chip tone="quiet">{g.why}</Chip></li>)}
          </ul>
        </details>
      )}
      {error && <p className="rounded-md bg-wash px-2 py-1 text-xs">{error}</p>}
    </div>
  );
}
