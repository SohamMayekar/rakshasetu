// Chips. "Attention" is ink inversion (the row needs you); everything else is quiet.
// Method chips are the receipts' first word (PRD F-C13): who produced this value.

import type { ReactNode } from "react";

export function Chip({ tone = "neutral", children, title }: { tone?: "attention" | "neutral" | "quiet"; children: ReactNode; title?: string }) {
  const cls = {
    attention: "bg-ink text-paper",
    neutral: "border border-line bg-paper text-ink-2",
    quiet: "bg-wash text-ink-2",
  }[tone];
  return <span title={title} className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${cls}`}>{children}</span>;
}

export type Method = "ai" | "rule" | "human" | "partner" | "fixture";
const METHOD: Record<Method, { label: string; title: string }> = {
  ai: { label: "AI", title: "Read out of the words by AI (or speech to text), with the exact quote" },
  rule: { label: "Rule", title: "From fixed rules: word lists, the map of village names, the scoring or the priority rules" },
  human: { label: "Person", title: "Typed, checked or moved by a person" },
  partner: { label: "Partner", title: "Sent by another team's system" },
  fixture: { label: "Recording", title: "A recorded result, not a live call" },
};

export function MethodChip({ method }: { method: Method }) {
  const m = METHOD[method];
  return (
    <span title={m.title} className={`inline-flex items-center rounded-md bg-wash px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-ink-2 ${method === "ai" ? "italic" : ""}`}>
      {m.label}
    </span>
  );
}

// ● checked by a person · ○ not checked yet · amber ○ the quote check failed or the keywords disagree.
export function Check({ state, title }: { state: "checked" | "unchecked" | "amber"; title?: string }) {
  const glyph = state === "checked" ? "●" : "○";
  const cls = state === "amber" ? "text-amber" : state === "checked" ? "text-ink" : "text-ink-3";
  const t = title ?? { checked: "Checked by a person", unchecked: "Not checked yet", amber: "Check this: the quote wasn't found, or the keywords disagree" }[state];
  return <span aria-label={t} title={t} className={`text-xs leading-none ${cls}`}>{glyph}</span>;
}

const CHANNEL: Record<string, string> = { voice: "Voice", whatsapp: "WhatsApp", spreadsheet: "Sheet", web_form: "Typed at the desk", partner: "Partner system" };

export function ChannelTag({ channel }: { channel: string }) {
  return <span className="text-[11px] font-semibold text-ink-3">{CHANNEL[channel] ?? channel}</span>;
}
