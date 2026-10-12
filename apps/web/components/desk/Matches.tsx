"use client";

// Likely duplicates (PRD F-D1/F-D2): the rules' reasons side by side, and a person decides. "Merge" folds the
// newer case into the older one (undoable); "Not the same household" blocks the pair for good. A refused pair
// (different given names) is shown with the names that kept it apart, and can still be merged deliberately,
// with a reason. Nothing here is decided by a model.

import { useState } from "react";

import { Because, Button, Chip } from "@/components/ui";
import { api, type Case, type Suggestion } from "@/lib/api";

function Side({ c, label }: { c: Case | undefined; label: string }) {
  if (!c) return <div className="text-xs text-ink-3">{label}: not in your scope</div>;
  return (
    <div className="min-w-0 flex-1 text-xs">
      <p className="tabular font-medium">{c.public_id}</p>
      <p className="truncate">{c.summary}</p>
      <p className="truncate text-ink-2">{c.location_text ?? "no location"} · {c.location_confidence ?? "no pin"}</p>
      {Array.isArray(c.attributes?.person_names) && (c.attributes.person_names as string[]).length > 0 &&
        <p className="truncate text-ink-2">{(c.attributes.person_names as string[]).join(", ")}</p>}
    </div>
  );
}

export function Matches({ c, suggestions, lookup, canDecide, onDone }: {
  c: Case; suggestions: Suggestion[]; lookup: (id: number) => Case | undefined; canDecide: boolean;
  onDone: (keptCaseId?: number) => void;
}) {
  const [asking, setAsking] = useState<{ id: number; kind: "merge" | "reject" } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mine = suggestions.filter((s) => s.case_id === c.id || s.candidate_case_id === c.id);
  if (!mine.length) return null;
  // Likely duplicates are shown in full; pairs the rules kept apart (names differ) fold into one line,
  // because in a busy village most neighbours look alike on village + landmark alone.
  const open = mine.filter((s) => s.strength !== "refused");
  const refused = mine.filter((s) => s.strength === "refused");

  const decide = async (s: Suggestion, kind: "merge" | "reject", reason: string | null) => {
    setError(null);
    try {
      if (kind === "merge") {
        const r = await api<{ kept: number }>(`/v1/merge-suggestions/${s.id}/accept`, { method: "POST", json: { reason } });
        onDone(r.kept);
      } else {
        await api(`/v1/merge-suggestions/${s.id}/reject`, { method: "POST", json: { reason } });
        onDone();
      }
      setAsking(null);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const card = (s: Suggestion) => {
    const other = s.case_id === c.id ? s.candidate_case_id : s.case_id;
    const refused = s.strength === "refused";
    const names = s.conflicts.filter((x) => x.startsWith("name ")).map((x) => x.slice(5));
    return (
      <div key={s.id} className="rounded-2xl border border-line p-3.5">
        <p className="flex items-center gap-2 text-sm font-medium">
          {refused ? <>Not merged with {s.case_id === c.id ? s.candidate : s.public_id} {names.map((n) => <Chip key={n} tone="attention">{n}</Chip>)}</>
                   : <>Likely same household as {s.case_id === c.id ? s.candidate : s.public_id} <Chip tone="quiet">{s.strength}</Chip></>}
        </p>
        <Because>{s.reasons.join(" · ")}{refused && !s.reasons.some((r) => r.startsWith("same phone")) ? ". Village and headcount alone are weak." : ""}</Because>
        <div className="mt-2 flex gap-3 rounded-xl bg-wash p-2.5">
          <Side c={c} label="This case" /><span className="self-center text-ink-3">↔</span><Side c={lookup(other)} label="The other case" />
        </div>
        {canDecide && (asking?.id === s.id ? (
          <form className="mt-2 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); decide(s, asking.kind, String(new FormData(e.currentTarget).get("reason") || "") || null); }}>
            <input name="reason" required={refused && asking.kind === "merge"} minLength={3} autoFocus
                   placeholder={asking.kind === "merge" ? (refused ? "Why merge them anyway? (logged)" : "Reason (optional, logged)") : "Why not? (optional, logged)"}
                   className="h-8 min-w-0 flex-1 rounded-lg border border-line px-2 text-sm" />
            <Button size="sm" variant="primary" type="submit">{asking.kind === "merge" ? "Merge" : "Not the same household"}</Button>
            <Button size="sm" variant="quiet" type="button" onClick={() => setAsking(null)}>Cancel</Button>
          </form>
        ) : (
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant={refused ? "secondary" : "primary"} onClick={() => setAsking({ id: s.id, kind: "merge" })}>
              {refused ? "Merge anyway" : "Merge"}
            </Button>
            {!refused && <Button size="sm" onClick={() => setAsking({ id: s.id, kind: "reject" })}>Not the same household</Button>}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="mb-4 space-y-3">
      {open.map(card)}
      {refused.length > 0 && (
        <details className="rounded-2xl border border-line px-3.5 py-2.5 text-sm" open={refused.length === 1 && open.length === 0}>
          <summary className="cursor-pointer select-none">
            Kept apart from {refused.length === 1 ? (refused[0].case_id === c.id ? refused[0].candidate : refused[0].public_id) : `${refused.length} cases`}:
            {" "}the names differ
          </summary>
          <div className="mt-2 space-y-3">{refused.map(card)}</div>
        </details>
      )}
      {error && <p className="rounded-md bg-wash px-2 py-1 text-xs">{error}</p>}
    </div>
  );
}
