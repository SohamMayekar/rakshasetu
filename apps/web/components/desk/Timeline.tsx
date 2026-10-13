"use client";

// Timeline & evidence (PRD F-C2, F-C11): everything that happened to this case, in order, in plain words.
// Each report shows its channel, its words in the caller's own script (with the hovered fact's quote lit up),
// its pipeline receipt, and its evidence inline: the clip and its transcript, the message as received, the
// spreadsheet row (file name, row number); and the case's own records: rescues (with where the team was), radio
// logs, merges. Each opens its stored file. Every file is re-hashed when the drawer opens: ✓ means it still
// matches the audit log.

import {
  AlarmClock, Archive, ArrowUpDown, Ban, CircleCheck, CirclePlus, Copy, Eye, Flag, GitMerge, Handshake, Inbox, Keyboard,
  LifeBuoy, type LucideIcon, MapPin, MessageCircle, Mic, PencilLine, PhoneIncoming, Plug, Presentation, Radio, RotateCcw,
  Sheet, ThumbsUp, Users,
} from "lucide-react";
import { useState } from "react";

import { Button, ChannelTag, Clock, Receipt } from "@/components/ui";
import { api, type Evidence, type PartnerNote, type Report, type TimelineEvent } from "@/lib/api";
import { withWords } from "@/lib/words";

function Undo({ mergeId, onDone }: { mergeId: number; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!open) return <Button size="sm" variant="quiet" onClick={() => setOpen(true)}>Undo merge</Button>;
  return (
    <form className="mt-1 flex flex-wrap gap-2" onSubmit={async (e) => {
      e.preventDefault();
      try {
        await api(`/v1/merges/${mergeId}/undo`, { method: "POST", json: { reason: String(new FormData(e.currentTarget).get("reason")) } });
        setOpen(false); onDone();
      } catch (x) { setError(x instanceof Error ? x.message : String(x)); }
    }}>
      <input name="reason" required minLength={3} autoFocus placeholder="Why undo? (logged)" className="field-compact min-w-0 flex-1" />
      <Button size="sm" variant="primary" type="submit">Undo merge</Button>
      <Button size="sm" variant="quiet" type="button" onClick={() => setOpen(false)}>Cancel</Button>
      {error && <span className="w-full text-small">{error}</span>}
    </form>
  );
}

function Highlight({ text, quote }: { text: string; quote: string | null }) {
  if (!quote) return <>{text}</>;
  const i = text.toLowerCase().indexOf(quote.toLowerCase());
  if (i < 0) return <>{text}</>;
  return <>{text.slice(0, i)}<mark className="rounded-md bg-ink px-1 text-paper">{text.slice(i, i + quote.length)}</mark>{text.slice(i + quote.length)}</>;
}

function Hash({ e }: { e: Evidence }) {
  if (!e.sha256) return null;
  const ok = e.file_ok !== false && e.chain_ok;
  return (
    <span className="tabular text-micro text-ink-3" title={`Fingerprint ${e.sha256}: the file is checked against the copy in the history`}>
      {ok ? "✓ unchanged since it was saved" : <b className="text-ink">✗ changed since it was saved</b>}
    </span>
  );
}

const OUTCOME: Record<string, string> = { rescued: "rescued, nobody left", partial: "someone still there",
  corroboration: "a second record of the same trip", nobody_here: "nobody here", couldnt_reach: "couldn't reach",
  other: "other: told the officer" };

function EvidenceItem({ e }: { e: Evidence }) {
  if (e.type === "audio") {
    return (
      <div className="mt-2 space-y-1">
        <audio controls preload="none" src={`/v1/evidence/${e.id}/file`} className="h-8 w-full" />
        <Hash e={e} />
      </div>
    );
  }
  if (e.type === "sheet_row") {
    const m = e.meta as { file_name?: string; row?: number; cells?: Record<string, string> };
    return (
      <details className="mt-2 rounded-xl border border-line bg-paper px-3 py-2 text-small">
        <summary className="cursor-pointer select-none">
          Spreadsheet row · <span className="font-medium">{m.file_name}</span> · row <span className="tabular">{m.row}</span>{" "}
          <a className="underline underline-offset-2" href={`/v1/evidence/${e.id}/file`} onClick={(x) => x.stopPropagation()}>file</a>
        </summary>
        <table className="mt-1.5 w-full">
          <tbody>
            {Object.entries(m.cells ?? {}).filter(([, v]) => v).map(([k, v]) => (
              <tr key={k}><td className="pr-2 align-top text-ink-3">{k}</td><td>{v}</td></tr>
            ))}
          </tbody>
        </table>
        <Hash e={e} />
      </details>
    );
  }
  const open = <a className="underline underline-offset-2" href={`/v1/evidence/${e.id}/file`} target="_blank" rel="noreferrer">open</a>;
  if (e.type === "transcript") {
    const m = e.meta as { by?: string; detail?: string };
    return (
      <p className="mt-1.5 text-small text-ink-2">
        Transcript · {m.by === "Fixture" ? "a recording's transcript, not live speech to text" : m.detail} · {open} <Hash e={e} />
      </p>
    );
  }
  if (e.type === "message") {
    const m = e.meta as { forwarded?: boolean };
    return <p className="mt-1.5 text-small text-ink-2">The {m.forwarded ? "forward" : "message"} as received · {open} <Hash e={e} /></p>;
  }
  if (e.type === "rescue") {
    const m = e.meta as { team?: string; outcome?: string; people_taken?: number | null; channel?: string;
                          team_position?: { lat: number; lng: number; from: string } | null; metres_from_pin?: number | null };
    const pos = m.team_position;
    return (
      <div className="mt-1 rounded-xl border border-line bg-paper px-3 py-2 text-small">
        <p>Rescue record · <b>{m.team}</b> · {OUTCOME[m.outcome ?? ""] ?? m.outcome}
          {m.people_taken != null && <> · {m.people_taken} taken</>} · via {m.channel} · {open}</p>
        <p className="text-ink-2">{pos
          ? <>Team at <span className="tabular">{pos.lat.toFixed(5)}, {pos.lng.toFixed(5)}</span> ({pos.from}){m.metres_from_pin != null && <> · <span className="tabular">{m.metres_from_pin.toLocaleString("en-IN")}</span> m from the family&rsquo;s place</>}</>
          : "No position for the team"}</p>
        <Hash e={e} />
      </div>
    );
  }
  if (e.type === "radio") {
    const m = e.meta as { team?: string; channel?: string; new_eta?: number | null; logged_by?: string; note?: string | null };
    return (
      <p className="mt-1.5 text-small text-ink-2">
        Radio log · {m.team} on {m.channel}{m.new_eta ? ` · ETA ${m.new_eta} min` : ""}{m.note ? ` · “${m.note}”` : ""} · logged by {m.logged_by} · {open} <Hash e={e} />
      </p>
    );
  }
  if (e.type === "partner_annotation") {
    const m = e.meta as { team?: string; kind?: string; value?: string; confidence?: number | null };
    return <p className="mt-1.5 text-small text-ink-2">Partner note · {m.team}: {m.kind} {withWords(String(m.value ?? ""))}{m.confidence != null ? ` · ${Number(m.confidence).toFixed(2)}` : ""} · {open} <Hash e={e} /></p>;
  }
  if (e.type === "merge") {
    const m = e.meta as { source?: string; target?: string };
    return <p className="mt-1.5 text-small text-ink-2">Merge record · {m.source} into {m.target} · {open} <Hash e={e} /></p>;
  }
  return null;
}

// A partner's credibility note sits on THAT item, as a chip: it never blocks a dispatch or lowers a priority.
function Notes({ e, notes }: { e: Evidence; notes: PartnerNote[] }) {
  const mine = notes.filter((n) => n.kind === "credibility" && n.evidence_id === e.id);
  if (!mine.length) return null;
  return (
    <p className="mt-1 flex flex-wrap gap-1.5">
      {mine.map((n) => (
        <span key={n.id} className="rounded-full border border-line px-2 py-0.5 text-micro text-ink-2" title={n.explanation ?? ""}>
          {n.team}: {n.value}{n.confidence != null ? ` · ${n.confidence.toFixed(2)}` : ""}{n.explanation ? ` · ${n.explanation}` : ""}
        </span>
      ))}
    </p>
  );
}

function ReportCard({ r, evidence, quote, notes }: { r: Report; evidence: Evidence[]; quote: string | null; notes: PartnerNote[] }) {
  const words = r.transcript ?? r.text;
  return (
    <div className="mt-2 rounded-xl rounded-tl-md bg-wash px-3.5 py-3">
      <p className="flex flex-wrap items-center gap-x-2 text-small text-ink-2">
        <ChannelTag channel={r.channel} /><Clock iso={r.received_at} />
        {r.reporter_relation && !["unknown", "forwarder"].includes(r.reporter_relation) && <span>{r.reporter_relation}</span>}
        {r.is_forward && <span>a forward</span>}
        {r.reporter_phone_masked && <span className="tabular">{r.reporter_phone_masked}</span>}
      </p>
      {words ? <p className="mt-1.5 whitespace-pre-line text-body leading-relaxed" lang={r.language ?? undefined}><Highlight text={words} quote={quote} /></p>
             : <p className="mt-1 text-body text-ink-3">voice only: listen to it</p>}
      {r.receipt && <div className="mt-1"><Receipt steps={r.receipt} /></div>}
      {evidence.map((e) => <div key={e.id}><EvidenceItem e={e} /><Notes e={e} notes={notes} /></div>)}
    </div>
  );
}

// One quiet icon per kind of event (m60), so the feed can be scanned; the words still say what happened.
const CHANNEL_ICON: Record<string, LucideIcon> = { voice: Mic, whatsapp: MessageCircle, spreadsheet: Sheet, partner: Plug, web_form: Keyboard };
const EVIDENCE_ICON: Record<string, LucideIcon> = { rescue: LifeBuoy, radio: Radio, merge: GitMerge, partner_annotation: Handshake };
function iconFor(type: string, channel?: string, evidenceType?: string): LucideIcon {
  if (type === "report.received") return CHANNEL_ICON[channel ?? ""] ?? Inbox;
  if (type === "evidence.added") return EVIDENCE_ICON[evidenceType ?? ""] ?? Inbox;
  if (type === "report.callback_added") return PhoneIncoming;
  if (type === "case.created") return CirclePlus;
  if (type === "case.checked") return CircleCheck;
  if (type === "case.updated") return PencilLine;
  if (type.startsWith("case.location")) return MapPin;
  if (["case.merged", "case.absorbed", "case.unmerged"].includes(type)) return GitMerge;
  if (type === "merge.suggested") return Copy;
  if (type.startsWith("merge.")) return Ban;
  if (type.startsWith("case.priority")) return ArrowUpDown;
  if (type === "case.reopened") return RotateCcw;
  if (type === "case.closed" || type === "case.cancelled") return Archive;
  if (type === "assignment.overdue") return AlarmClock;
  if (type === "assignment.contact") return Radio;
  if (type === "assignment.reached") return Flag;
  if (type === "assignment.acknowledged") return CircleCheck;
  if (type.startsWith("assignment.")) return Users;
  if (type === "rescue.confirmed") return ThumbsUp;
  if (type.startsWith("rescue.")) return LifeBuoy;
  if (type === "contact.revealed") return Eye;
  if (type.startsWith("partner.")) return Handshake;
  if (type.startsWith("demo.")) return Presentation;
  return Inbox;
}

function Dot({ icon: Icon }: { icon: LucideIcon }) {
  return <span className="mt-px grid size-7 shrink-0 place-items-center rounded-full bg-wash text-ink-2" aria-hidden><Icon className="size-3.5" strokeWidth={2} /></span>;
}

// A report's own evidence (clip, transcript, message, sheet row) shows inside its report card; a case's own
// records (rescue, radio log, merge) show under their "Evidence kept" line.

export function Timeline({ events, evidence, reports, quote, canUndo = false, onChanged, notes = [] }: {
  events: TimelineEvent[]; evidence: Evidence[]; reports: Report[]; quote: string | null; canUndo?: boolean; onChanged?: () => void;
  notes?: PartnerNote[];
}) {
  const reportById = new Map(reports.map((r) => [r.id, r]));
  const evidenceById = new Map(evidence.map((x) => [x.id, x]));
  const own = (e: TimelineEvent) => e.evidence_id != null ? evidenceById.get(e.evidence_id) : undefined;
  return (
    <ol className="space-y-3.5">
      {events.filter((e) => e.type !== "evidence.added" || (own(e) && own(e)!.report_id == null)).map((e) => {
        const r = e.type === "report.received" && e.report_id != null ? reportById.get(e.report_id) : undefined;
        const item = e.type === "evidence.added" ? own(e) : undefined;
        return (
          <li key={e.seq} className="flex gap-3 text-body">
            <Dot icon={iconFor(e.type, r?.channel, item?.type)} />
            <div className="min-w-0 flex-1">
              {item ? (   // a case's own record: the item itself is the line
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1"><EvidenceItem e={item} /><Notes e={item} notes={notes} /></div>
                  <span className="shrink-0 pt-2 text-small text-ink-3"><Clock iso={e.at} /></span>
                </div>
              ) : (
                <p className="flex items-start justify-between gap-2 pt-1">
                  <span className="min-w-0">
                    {withWords(e.line)}
                    {e.reason && <span className="text-ink-2"> · &ldquo;{e.reason}&rdquo;</span>}
                    {e.type === "case.merged" && e.undone && <span className="text-ink-3"> · undone</span>}
                    {e.type === "case.merged" && !e.undone && canUndo && e.merge_id != null && (
                      <span className="block"><Undo mergeId={e.merge_id} onDone={() => onChanged?.()} /></span>
                    )}
                  </span>
                  <span className="shrink-0 text-small text-ink-3"><Clock iso={e.at} /></span>
                </p>
              )}
              {r && <ReportCard r={r} evidence={evidence.filter((x) => x.report_id === r.id)} quote={quote} notes={notes} />}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
