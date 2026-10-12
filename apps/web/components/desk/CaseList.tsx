"use client";

// The left column. m33: the cases in scope, by priority. m34 turns it into "Needs you now" (attention rows only).

import { Ago, Priority } from "@/components/ui";
import type { Case } from "@/lib/api";

const ORDER = { P1: 0, P2: 1, P3: 2, P4: 3 };

export function sortForDesk(a: Case, b: Case) {
  return ORDER[a.priority] - ORDER[b.priority] || (a.p1_rank ?? 9) - (b.p1_rank ?? 9) || a.queue_since.localeCompare(b.queue_since);
}

export function CaseList({ cases, selected, onSelect }: { cases: Case[]; selected: number | null; onSelect: (id: number) => void }) {
  return (
    <ol className="divide-y divide-line">
      {cases.map((c) => (
        <li key={c.id}>
          <button onClick={() => onSelect(c.id)} aria-current={selected === c.id}
                  className={`block w-full px-4 py-2.5 text-left hover:bg-wash ${selected === c.id ? "bg-wash" : ""}`}>
            <span className="flex items-baseline justify-between gap-2">
              <span className="flex items-baseline gap-2"><Priority level={c.priority} /><span className="tabular font-medium">{c.public_id}</span></span>
              <span className="text-xs text-ink-3"><Ago iso={c.queue_since} /></span>
            </span>
            <span className="mt-0.5 block truncate text-sm">{c.summary}</span>
            <span className="block truncate text-xs text-ink-2">{c.location_text ?? "no location yet"}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}
