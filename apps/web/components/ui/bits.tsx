"use client";

// Pieces of the desk: the "new items" pill (the list never re-sorts under the cursor), empty states,
// the pipeline receipt line, the confidence circle legend and the judge-legibility caption.

import type { ReactNode } from "react";

import { STEP_WORD } from "@/lib/words";

import { type Method, MethodChip } from "./chips";

export function NewPill({ count, onShow }: { count: number; onShow: () => void }) {
  if (count <= 0) return null;
  return (
    <button onClick={onShow} className="mx-auto flex items-center gap-1 rounded-full bg-ink px-3 py-1 text-small font-medium text-paper shadow-sm">
      <span aria-hidden>▲</span><span className="tabular">{count}</span> new: show
    </button>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="px-6 py-10 text-center text-body text-ink-2">{children}</div>;
}

export type ReceiptStep = { step: string; by: string; detail: string };

// "STT·AI Saaras 2.1 s → extract·AI 6 fields → quotes ✓·Rule → place·Rule Medium → P1·Rule"
export function Receipt({ steps }: { steps: ReceiptStep[] }) {
  if (!steps?.length) return null;
  return (
    <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-micro leading-snug text-ink-3">
      {steps.map((s, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          {i > 0 && <span aria-hidden>→</span>}
          <span>{STEP_WORD[s.step] ?? s.step}</span>
          <MethodChip method={(s.by.toLowerCase() as Method)} />
          <span className="text-ink-2">{s.detail.replace(/language model/g, "AI reading")}</span>
        </span>
      ))}
    </p>
  );
}

// Circles always, never a bare pin; dashed = Low (PRD F-L4, §13.5).
export function CircleLegend() {
  const items: [string, boolean][] = [["within ~150 m", false], ["within ~300 m", false], ["somewhere in ~1.5 km", true]];
  return (
    <div className="flex gap-4 text-small text-ink-2">
      {items.map(([label, dashed]) => (
        <span key={label} className="inline-flex items-center gap-1.5">
          <svg width="16" height="16" aria-hidden><circle cx="8" cy="8" r="6.5" fill="rgba(17,17,17,0.06)" stroke="#111" strokeWidth="1.2" strokeDasharray={dashed ? "2.5 2" : undefined} /></svg>
          {label}
        </span>
      ))}
    </div>
  );
}

// The judge-legibility caption (DEMO_MODE only): one plain sentence about what just happened, from a template.
export function Caption({ text }: { text: string | null }) {
  if (!text) return null;
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex justify-center px-4">
      <p className="max-w-3xl rounded-xl bg-ink/90 px-4 py-2 text-center text-body text-paper shadow-lg">{text}</p>
    </div>
  );
}
