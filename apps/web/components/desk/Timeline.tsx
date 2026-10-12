"use client";

// Timeline & evidence (PRD F-C2, F-C11): everything that happened to this case, in order, in plain words.
// Each report shows its channel, its words in the caller's own script (with the hovered fact's quote lit up),
// its pipeline receipt, and its evidence inline: the audio clip, the spreadsheet row with file name, row number
// and sha256. Every file is re-hashed when the drawer opens: ✓ means it still matches the audit log.

import { ChannelTag, Clock, Receipt } from "@/components/ui";
import type { Evidence, Report, TimelineEvent } from "@/lib/api";

function Highlight({ text, quote }: { text: string; quote: string | null }) {
  if (!quote) return <>{text}</>;
  const i = text.toLowerCase().indexOf(quote.toLowerCase());
  if (i < 0) return <>{text}</>;
  return <>{text.slice(0, i)}<mark className="rounded-sm bg-ink px-0.5 text-paper">{text.slice(i, i + quote.length)}</mark>{text.slice(i + quote.length)}</>;
}

function Hash({ e }: { e: Evidence }) {
  if (!e.sha256) return null;
  const ok = e.file_ok !== false && e.chain_ok;
  return (
    <span className="tabular text-[11px] text-ink-3" title={`sha256 ${e.sha256}`}>
      sha256 {e.sha256.slice(0, 12)}… {ok ? "✓ matches the audit log" : <b className="text-ink">✗ does not match the audit log</b>}
    </span>
  );
}

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
      <details className="mt-2 rounded-md border border-line px-2 py-1.5 text-xs">
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
  return null;
}

function ReportCard({ r, evidence, quote }: { r: Report; evidence: Evidence[]; quote: string | null }) {
  const words = r.transcript ?? r.text;
  return (
    <div className="mt-1.5 rounded-lg bg-wash px-3 py-2">
      <p className="flex flex-wrap items-center gap-x-2 text-xs text-ink-2">
        <ChannelTag channel={r.channel} /><Clock iso={r.received_at} />
        {r.reporter_relation && r.reporter_relation !== "unknown" && <span>{r.reporter_relation}</span>}
        {r.is_forward && <span>a forward</span>}
        {r.reporter_phone_masked && <span className="tabular">{r.reporter_phone_masked}</span>}
      </p>
      {words ? <p className="mt-1 whitespace-pre-line text-sm leading-snug" lang={r.language ?? undefined}><Highlight text={words} quote={quote} /></p>
             : <p className="mt-1 text-sm text-ink-3">audio only: listen</p>}
      {r.receipt && <div className="mt-1"><Receipt steps={r.receipt} /></div>}
      {evidence.map((e) => <EvidenceItem key={e.id} e={e} />)}
    </div>
  );
}

const QUIET = new Set(["evidence.added"]);   // shown inline with their report instead

export function Timeline({ events, evidence, reports, quote }: {
  events: TimelineEvent[]; evidence: Evidence[]; reports: Report[]; quote: string | null;
}) {
  const reportById = new Map(reports.map((r) => [r.id, r]));
  return (
    <ol className="space-y-2.5">
      {events.filter((e) => !QUIET.has(e.type)).map((e) => {
        const r = e.type === "report.received" && e.report_id != null ? reportById.get(e.report_id) : undefined;
        return (
          <li key={e.seq} className="text-sm">
            <p className="flex gap-2">
              <span className="w-11 shrink-0 text-xs text-ink-3"><Clock iso={e.at} /></span>
              <span>
                {e.line}
                {e.reason && <span className="text-ink-2"> · &ldquo;{e.reason}&rdquo;</span>}
              </span>
            </p>
            {r && <div className="pl-[52px]"><ReportCard r={r} evidence={evidence.filter((x) => x.report_id === r.id)} quote={quote} /></div>}
          </li>
        );
      })}
    </ol>
  );
}
