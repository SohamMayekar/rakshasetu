"use client";

// The rescue sheet (PRD F-S3), shared by the responder app and the desk's radio record ("via radio"). Usable
// with wet hands: one number with − and +, then one of three big answers. No codes, nothing asked of the family.

import { useState } from "react";

export type RescueBody = {
  people_taken?: number | null; anyone_left?: "yes" | "no" | "dont_know" | null;
  outcome?: "nobody_here" | "couldnt_reach" | "other" | null; reason?: string | null;
};

const REASONS: [string, string][] = [["water_current", "Water or current"], ["road_bridge", "Road or bridge"],
                                     ["night", "Night"], ["other", "Other"]];

export function RescueSheet({ reported, onRecord, big = true }: {
  reported: number | null; onRecord: (body: RescueBody, label: string) => void; big?: boolean;
}) {
  const [taken, setTaken] = useState<number>(reported ?? 1);
  const [more, setMore] = useState<null | "reach" | "other">(null);
  const h = big ? "min-h-16 text-lg" : "min-h-10 text-sm";
  const btn = (primary = false) => `flex w-full items-center justify-center rounded-2xl px-4 font-semibold ${h} ${
    primary ? "bg-ink text-paper" : "border-2 border-ink bg-paper text-ink"}`;
  return (
    <div className="space-y-4">
      <div>
        <p className={big ? "text-lg font-medium" : "text-sm font-medium"}>How many people did you take?</p>
        <div className="mt-2 flex items-center gap-3">
          <button className={`${btn()} !w-20`} onClick={() => setTaken(Math.max(0, taken - 1))} aria-label="One fewer">−</button>
          <span className={`tabular ${big ? "text-5xl" : "text-3xl"} w-20 text-center font-semibold`} aria-live="polite">{taken}</span>
          <button className={`${btn()} !w-20`} onClick={() => setTaken(taken + 1)} aria-label="One more">+</button>
        </div>
        {reported != null && <p className="mt-1 text-sm text-ink-2">Reported: {reported}</p>}
      </div>
      <div>
        <p className={big ? "text-lg font-medium" : "text-sm font-medium"}>Is anyone still there?</p>
        <div className="mt-2 grid grid-cols-3 gap-2">
          <button className={btn(true)} onClick={() => onRecord({ people_taken: taken, anyone_left: "no" }, `Rescued ${taken} · nobody left`)}>No</button>
          <button className={btn()} onClick={() => onRecord({ people_taken: taken, anyone_left: "yes" }, `Took ${taken} · someone still there`)}>Yes</button>
          <button className={btn()} onClick={() => onRecord({ people_taken: taken, anyone_left: "dont_know" }, `Took ${taken} · don't know`)}>Don&rsquo;t know</button>
        </div>
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer select-none py-2 underline underline-offset-4">Couldn&rsquo;t do it?</summary>
        <div className="mt-2 space-y-2">
          <button className={btn()} onClick={() => onRecord({ outcome: "nobody_here" }, "Nobody here")}>Nobody here</button>
          <button className={btn()} onClick={() => setMore(more === "reach" ? null : "reach")}>Couldn&rsquo;t reach</button>
          {more === "reach" && (
            <div className="grid grid-cols-2 gap-2">
              {REASONS.map(([k, label]) => <button key={k} className={btn()} onClick={() => onRecord({ outcome: "couldnt_reach", reason: k }, `Couldn't reach · ${label.split(" · ")[0]}`)}>{label}</button>)}
            </div>
          )}
          <button className={btn()} onClick={() => setMore(more === "other" ? null : "other")}>Other: tell the officer</button>
          {more === "other" && (
            <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); onRecord({ outcome: "other", reason: String(new FormData(e.currentTarget).get("reason")) }, "Told the officer"); }}>
              <textarea name="reason" required minLength={3} rows={3} placeholder="What should the officer know?" className="w-full rounded-xl border border-line p-3" />
              <button className={btn(true)}>Send to the officer</button>
              <p className="text-xs text-ink-3">No automatic message goes to the family after this.</p>
            </form>
          )}
        </div>
      </details>
    </div>
  );
}
