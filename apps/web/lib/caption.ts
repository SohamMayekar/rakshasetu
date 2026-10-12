// The judge-legibility caption (DEMO_MODE, the projector desk only): one plain sentence about the most important
// thing in the last 1-second frame of events, from a template over the event's own data. It never speaks for the
// language model; it says what the rules or a person did, and why, in the words the timeline uses.

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

const TEMPLATES: Record<string, (d: D, c: Ctx, e: Envelope) => string | null> = {
  "chain.genesis": () => "The demo was reset: the history starts again from here.",
  "demo.language_model": (d) => d.on
    ? "AI reading is back on. It only reads facts out of the words; rules still decide."
    : "AI reading is off. Reports still become cases: fixed word rules read them, and the chips say Rule.",
  "demo.surge_started": (d) => `A rush of made-up reports started: ${s(d.rate)} a second, already sorted into fields, so no AI is called.`,
  "demo.clip_played": (d) => `A recorded clip went in the same way a phone sends one${d.synthetic_voice ? " (a synthetic voice)" : ""}.`,
  "import.uploaded": (d) => `A volunteer sheet arrived: ${s(d.rows)} rows. Its columns are matched by name, then a person confirms them.`,
  "import.progress": (d) => `Reading the sheet: ${s(d.rows_done)} of ${s(d.rows_total)} rows · ${s(d.new_cases)} new cases · ${s(d.merged)} merged · ${s(d.to_check)} to check. The list holds still.`,
  "import.completed": (d) => s(d.summary) || null,
  "case.created": (d, c, e) => {
    const clip = clips.get(d.report_id);
    const how = clip != null ? `The recorded clip${clip ? " (a synthetic voice)" : ""}`
      : CHANNEL[s((e as unknown as { channel?: string }).channel)] ?? "A report";
    const why = list(d.priority_reasons);
    return `${how} became ${s(d.public_id)}, ${priorityWord(s(d.priority))}${why ? ` because ${why}` : ""}. Rules set the priority; every fact keeps its quote.`;
  },
  "case.checked": (d, c, e) => (d.seeded ? null : `${s(d.checked_by) || "A person"} checked ${c.pub(e.data.case_id)}: its facts are now confirmed by a person.`),
  "merge.suggested": (d, c, e) => `${s(d.line).replace(/^Likely same household as /, `${c.pub(e.data.case_id)} is likely the same household as `)}. A person decides.`,
  "merge.refused": (d, c, e) => s(d.line).replace(/^Not merged with /, `${c.pub(e.data.case_id)} was not merged with `),
  "case.merged": (d) => d.kind === "auto"
    ? `${s(d.source)} was folded into ${s(d.target)} automatically: same phone and the same place. Undo restores both exactly.`
    : `A person merged ${s(d.source)} into ${s(d.target)}: ${list(d.reasons)}. Undo restores both exactly.`,
  "assignment.created": (d, c, e) => `${s(d.team)} now owns ${c.pub(e.data.case_id)}.${d.demo_clock ? " Its timer runs on the demo clock, 60× faster." : ""} Nobody else is sent unless an officer decides.`,
  "assignment.contact": (d) => `${s(d.by)} logged radio contact with ${s(d.team)} on ${s(d.channel)}${d.new_eta ? `, ETA ${s(d.new_eta)} min` : ""}. Only real contact resets the timer.`,
  "assignment.acknowledged": (d, c, e) => `${s(d.team)} acknowledged ${c.pub(e.data.case_id)}${d.eta_minutes ? `, ETA ${s(d.eta_minutes)} min` : ""}.`,
  "assignment.reached": (d, c, e) => `${s(d.team)} reached ${c.pub(e.data.case_id)}.`,
  "assignment.overdue": (d, c, e) => `${s(d.team)} has gone quiet past its check-in. ${c.pub(e.data.case_id)} stays with ${s(d.team)}: nothing is taken away automatically; an officer decides.`,
  "escalation.raised": (d) => s(d.line) || null,
  "assignment.reassigned": (d, c, e) => `${c.pub(e.data.case_id)} moved from ${s(d.from_team)} to ${s(d.to_team)}, by a person.${d.standdown_owed ? ` ${s(d.from_team)} owes a stand-down.` : ""}`,
  "rescue.partial": (d, c, e) => `${s(d.team)} took ${s(d.people_taken)}${d.remaining != null ? `; ${s(d.remaining)} still there` : "; someone may still be there"}. ${c.pub(e.data.case_id)} goes back to the top with its original time.`,
  "rescue.recorded": (d) => `Rescued ${s(d.total_taken ?? d.people_taken)} of ${s(d.people_reported ?? d.total_taken)}. It closes after a review window unless something blocks it. The family may confirm; they never have to.`,
  "rescue.nobody_here": (d, c, e) => `${s(d.team)} found nobody there. ${c.pub(e.data.case_id)} goes back as Urgent: search the circle, ask for a new place.`,
  "rescue.couldnt_reach": (d, c, e) => `${s(d.team)} couldn't reach ${c.pub(e.data.case_id)} (${s(d.reason)}). It stays open, with why.`,
  "rescue.confirmed": (d) => `The family confirmed ${s(d.people_taken)} rescued, from the phone that reported.`,
  "rescue.disputed": (d, c, e) => `The family says not everyone was rescued. ${c.pub(e.data.case_id)} can't close until an officer radios the team.`,
  "case.reopened": (d, c, e) => `${c.pub(e.data.case_id)} reopened: the person on site says they weren't rescued. Back to the top as Urgent.`,
  "case.priority_overridden": (d, c, e) => `${s(d.by)} set ${c.pub(e.data.case_id)} to ${priorityWord(s(d.to))} (the rules said ${priorityWord(s(d.rules_said))}): “${s(e.data.reason)}”. Later facts won't undo a person's call.`,
  "case.priority_released": (d, c, e) => `${c.pub(e.data.case_id)} is back with the rules: ${priorityWord(s(d.to))}.`,
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
    return `Under load: ${simulated.size} made-up reports in the last second. The list holds still; new rows wait behind the pill.`;
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
