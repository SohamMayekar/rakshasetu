"use client";

// The case drawer (PRD F-C2), titled with the PS's words. m33 shows the case and its because-lines;
// m35 fills in receipts, the timeline with evidence, and the actions.

import { Because, Button, Estimate, Priority, Section } from "@/components/ui";
import type { Case } from "@/lib/api";

export function Drawer({ c, onClose }: { c: Case; onClose: () => void }) {
  return (
    <aside className="fixed inset-0 z-40 flex flex-col bg-paper md:static md:h-full md:w-[440px] md:shrink-0 md:border-l md:border-line" aria-label={`Case ${c.public_id}`}>
      <div className="flex items-start justify-between border-b border-line px-5 py-4">
        <div>
          <p className="flex items-baseline gap-2"><Priority level={c.priority} /><span className="tabular text-xl font-semibold tracking-tight">{c.public_id}</span></p>
          <p className="mt-1 text-sm">{c.summary}</p>
          {c.priority_reasons.length > 0 && <Because>{c.priority_reasons.join(" · ")}</Because>}
        </div>
        <Button variant="quiet" size="sm" onClick={onClose} aria-label="Close">Close</Button>
      </div>
      <div className="flex-1 overflow-y-auto px-5">
        <Section title="Assignment"><p className="text-sm text-ink-2">No team yet.</p></Section>
        <Section title="Facts">
          <dl className="grid grid-cols-[96px_1fr] gap-y-1.5 text-sm">
            <dt className="text-ink-3">People</dt><dd><Estimate value={c.people_count} kind={c.people_count_kind} /></dd>
            <dt className="text-ink-3">Where</dt><dd>{c.location_text ?? "not known yet"}<Because>{c.location_method}</Because></dd>
            <dt className="text-ink-3">Needs</dt><dd>{c.needs.join(", ") || "—"}</dd>
            <dt className="text-ink-3">Vulnerable</dt><dd>{c.vulnerable.join(", ") || "—"}</dd>
            <dt className="text-ink-3">Situation</dt><dd>{c.hazards.join(", ") || "—"}</dd>
          </dl>
        </Section>
        <Section title="Timeline & evidence"><p className="text-sm text-ink-3">Arrives in m35.</p></Section>
        <Section title="Audit"><a className="text-sm underline underline-offset-2" href={`/audit?case=${c.id}`}>This case&rsquo;s events</a></Section>
      </div>
    </aside>
  );
}
