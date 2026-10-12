// The glossary in code (docs/SIMPLIFY_PLAN.md): the plain words every screen uses. The API keeps its own short
// codes ("unchecked P1", "Assign → SDRF Boat 2 · 2.2 km · boat"), which tests and partners rely on; screens say
// them through these functions, so a judge reads "Urgent · not checked yet" and "Send SDRF Boat 2".

import type { Level } from "@/components/ui/priority";

export const PRIORITY_WORD: Record<Level, string> = { P1: "Urgent", P2: "High", P3: "Medium", P4: "Low" };
export const priorityWord = (p: string) => PRIORITY_WORD[p as Level] ?? p;

// "Never lost" etc. stay; every P-code in a sentence gets its word.
export const withWords = (s: string) => s.replace(/\bP([1-4])\b/g, (m) => PRIORITY_WORD[m as Level]);

/** A queue row's one chip, in plain words. */
export function plainChip(chip: string | null): string | null {
  if (!chip) return null;
  const late = chip.match(/^contact overdue (.+)$/);
  if (late) return `contact overdue ${late[1]}`;                 // CLAUDE.md copy: "contact overdue"
  const unowned = chip.match(/^no owner (.+)$/);
  if (unowned) return `no team for ${unowned[1]}`;
  const sheet = chip.match(/^(\d+) P1 without an owner$/);
  if (sheet) return `${sheet[1]} urgent without a team`;
  return ({
    "unchecked P1": "not checked yet",
    "needs location": "where exactly?",
    "possible duplicate": "maybe a repeat",
    "old report: confirm": "old report: confirm",
    "disputed: radio the team": "family says no: radio the team",
    "tell officer": "the team left a note",
    "nobody here: search": "nobody found: search",
  } as Record<string, string>)[chip] ?? chip;
}

/** A queue row's one action button, in plain words. */
export function plainAction(label: string): string {
  const send = label.match(/^Assign → (.+?) · ([\d.]+ km|no pin)/);
  if (send) return `Send ${send[1]} · ${send[2] === "no pin" ? "place unknown" : `${send[2]} away`}`;
  const match = label.match(/^Review match → (.+)$/);
  if (match) return `Same family as ${match[1]}?`;
  return ({
    "Assign a team": "Send a team",
    "Heard on radio": "Heard from them",
    "Fix pin": "Fix the place",
    "Check": "Mark checked",
    "Radio the team, then decide": "Radio the team",
  } as Record<string, string>)[label] ?? label;
}

/** The place's method sentence: "High · 150 m · matched …" → "within 150 m: matched …". */
export function plainPlace(method: string): string {
  return method.replace(/^(High|Medium|Low) · ([\d.,]+ k?m) · /, "within $2: ");
}

/** The pipeline receipt's step names. */
export const STEP_WORD: Record<string, string> = {
  stt: "speech to text", extract: "facts read", quotes: "quotes checked", place: "place found", priority: "priority set",
};

/** The audit log's event codes ("assignment.acknowledged") as words ("Assignment acknowledged"). */
export function plainEvent(action: string): string {
  const s = action.replace(/[._]/g, " ").replace(/\bp1\b/gi, "urgent");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export const DEMO_CLOCK = "the demo clock runs 60× faster";
