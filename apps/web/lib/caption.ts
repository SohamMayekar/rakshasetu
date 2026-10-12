// The projector caption (DEMO_MODE, the projector desk only): one short fact about the most important thing in the
// last 1-second frame of events ("BR-199 moved from SDRF Boat 2 to Fire & Rescue Boat 5, by a person."), from a
// template over the event's own data. Facts only, no narration (m74).

import type { Envelope } from "@/lib/live";
import { priorityWord } from "@/lib/words";

type D = Record<string, unknown>;
type Ctx = { pub: (caseId: unknown) => string };

const CHANNEL: Record<string, string> = { voice: "A voice report", web_form: "A typed report", partner: "A partner system's report",
  whatsapp: "A WhatsApp message", ivr: "A phone call" };
const s = (v: unknown) => (v == null ? "" : String(v));
const list = (v: unknown) => (Array.isArray(v) ? v.map(String).join(" · ") : "");

// Highest first: when a frame holds several events, the first that has a sentence wins.
const ORDER = ["chain.genesis", "demo.language_model", "demo.surge_started", "import.completed",
  "rescue.disputed", "case.reopened", "rescue.confirmed", "rescue.recorded", "rescue.partial", "rescue.nobody_here",
  "rescue.couldnt_reach", "assignment.reassigned", "assignment.overdue", "escalation.raised", "merge.refused", "case.merged",
  "merge.suggested", "case.created", "demo.clip_played", "assignment.contact", "assignment.created", "assignment.acknowledged",
  "assignment.reached", "case.checked", "case.priority_overridden", "case.priority_released", "case.closed",
  "import.uploaded", "import.progress"];

const first = (line: string) => line.split(". ")[0].replace(/\.$/, "");   // a backend line's first sentence

const TEMPLATES: Record<string, (d: D, c: Ctx, e: Envelope) => string | null> = {
  "chain.genesis": () => "The demo was reset.",
  "demo.language_model": (d) => (d.on ? "AI reading is on." : "AI reading is off: reports still become cases by word rules."),
  "demo.surge_started": (d) => `A rush started: ${s(d.rate)} made-up reports a second.`,
  "demo.clip_played": (d) => `A recorded clip was sent${d.synthetic_voice ? " (a synthetic voice)" : ""}.`,
  "import.uploaded": (d) => `A volunteer sheet arrived: ${s(d.rows)} rows.`,
  "import.progress": (d) => `Reading the sheet: ${s(d.rows_done)} of ${s(d.rows_total)} rows.`,
  "import.completed": (d) => s(d.summary) || null,
  "case.created": (d, c, e) => {
    const clip = clips.get(d.report_id);
    const how = clip != null ? `The recorded clip${clip ? " (a synthetic voice)" : ""}`
      : CHANNEL[s((e as unknown as { channel?: string }).channel)] ?? "A report";
    const why = list(d.priority_reasons);
    return `${how} became ${s(d.public_id)}, ${priorityWord(s(d.priority))}${why ? ` because ${why}` : ""}.`;
  },
  "case.checked": (d, c, e) => (d.seeded ? null : `${s(d.checked_by) || "A person"} checked ${c.pub(e.data.case_id)}.`),
  "merge.suggested": (d, c, e) => `${first(s(d.line)).split(":")[0].replace(/^Likely same household as /, `${c.pub(e.data.case_id)} is likely the same household as `)}.`,
  "merge.refused": (d, c, e) => first(s(d.line)).replace(/^Not merged with /, `${c.pub(e.data.case_id)} was not merged with `),
  "case.merged": (d) => d.kind === "auto"
    ? `${s(d.source)} was merged into ${s(d.target)}: same phone, same place.`
    : `A person merged ${s(d.source)} into ${s(d.target)}.`,
  "assignment.created": (d, c, e) => `${s(d.team)} now has ${c.pub(e.data.case_id)}.`,
  "assignment.contact": (d) => `Radio contact with ${s(d.team)}${d.new_eta ? `: there in ${s(d.new_eta)} min` : ""}.`,
  "assignment.acknowledged": (d, c, e) => `${s(d.team)} accepted ${c.pub(e.data.case_id)}${d.eta_minutes ? `: there in ${s(d.eta_minutes)} min` : ""}.`,
  "assignment.reached": (d, c, e) => `${s(d.team)} reached ${c.pub(e.data.case_id)}.`,
  "assignment.overdue": (d, c, e) => `${s(d.team)} missed its check-in. ${c.pub(e.data.case_id)} stays with it until an officer acts.`,
  "escalation.raised": (d) => (s(d.line) ? first(s(d.line)) : null),
  "assignment.reassigned": (d, c, e) => `${c.pub(e.data.case_id)} moved from ${s(d.from_team)} to ${s(d.to_team)}, by a person.`,
  "rescue.partial": (d, c, e) => `${s(d.team)} took ${s(d.people_taken)}${d.remaining != null ? `; ${s(d.remaining)} still there` : "; someone may still be there"}. ${c.pub(e.data.case_id)} is back at the top.`,
  "rescue.recorded": (d) => `Rescued ${s(d.total_taken ?? d.people_taken)} of ${s(d.people_reported ?? d.total_taken)}.`,
  "rescue.nobody_here": (d, c, e) => `${s(d.team)} found nobody at ${c.pub(e.data.case_id)}. It is back as Urgent.`,
  "rescue.couldnt_reach": (d, c, e) => `${s(d.team)} couldn't reach ${c.pub(e.data.case_id)} (${s(d.reason)}).`,
  "rescue.confirmed": (d) => `The family confirmed ${s(d.people_taken)} rescued.`,
  "rescue.disputed": (d, c, e) => `The family says not everyone was rescued. ${c.pub(e.data.case_id)} stays open.`,
  "case.reopened": (d, c, e) => `${c.pub(e.data.case_id)} reopened as Urgent: the family says they were not rescued.`,
  "case.priority_overridden": (d, c, e) => `${s(d.by)} set ${c.pub(e.data.case_id)} to ${priorityWord(s(d.to))}: “${s(e.data.reason)}”.`,
  "case.priority_released": (d, c, e) => `${c.pub(e.data.case_id)} is back to ${priorityWord(s(d.to))}.`,
  "case.closed": (d, c, e) => (d.resolution ? `${c.pub(e.data.case_id)} closed: ${s(d.resolution)}.` : null),
};

// What earlier frames said, for this frame's sentence: a voice report's case is made a second after the report
// arrives, and a new case's suggestion can arrive before the desk has loaded the case. Bounded.
const channel = new Map<unknown, string>();
const numbers = new Map<unknown, string>();
const clips = new Map<unknown, boolean>();   // report id → synthetic voice?
function remember<K, V>(m: Map<K, V>, k: K, v: V) {
  m.set(k, v);
  if (m.size > 500) m.delete(m.keys().next().value as K);
}

/** One sentence for this frame, or null. Surge and sheet rows are summarised, never captioned one by one. */
export function caption(events: Envelope[], pub: (caseId: number) => string | undefined): string | null {
  const simulated = new Set<unknown>(), sheet = new Set<unknown>();
  for (const e of events) {
    if (e.type === "case.created") remember(numbers, e.data.case_id, String(e.data.public_id));
    if (e.type === "demo.clip_played") remember(clips, e.data.report_id, Boolean(e.data.synthetic_voice));
    if (e.type !== "report.received") continue;
    if (e.data.simulated) simulated.add(e.data.report_id);
    if (e.data.channel === "spreadsheet") sheet.add(e.data.report_id);
    remember(channel, e.data.report_id, String(e.data.channel));
  }
  if (simulated.size >= 5) {
    return `A rush: ${simulated.size} made-up reports in the last second.`;
  }
  const ctx: Ctx = { pub: (id) => (typeof id === "number" ? pub(id) ?? numbers.get(id) ?? "This case" : "This case") };
  const ranked = events
    .filter((e) => ORDER.includes(e.type))
    .filter((e) => !(e.type === "case.created" && (simulated.has(e.data.report_id) || sheet.has(e.data.report_id))))
    .filter((e) => !(sheet.size && /^(merge\.|case\.merged)/.test(e.type)))   // the sheet's own merges: its summary says it
    .filter((e) => !(simulated.size && /^(merge\.|case\.merged)/.test(e.type)))
    .sort((a, b) => ORDER.indexOf(a.type) - ORDER.indexOf(b.type));
  for (const e of ranked) {
    const withChannel = e.type === "case.created" ? { ...e, channel: channel.get(e.data.report_id) } : e;
    const line = TEMPLATES[e.type]?.(e.data, ctx, withChannel as Envelope);
    if (line) return line;
  }
  return null;
}
