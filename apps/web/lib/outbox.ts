"use client";

// The responder's outbox (PRD F-C7): every tap gets its own id (its Idempotency-Key) and the time it really
// happened, is kept on the phone first ("Saved on phone"), waits 10 s so it can be undone (no confirm dialogs),
// then is sent and retried until the server has it ("Sent 02:32"). A retry can never act twice: the server
// answers a repeated key with the first answer.

export type Tap = {
  id: string; url: string; body: Record<string, unknown>; happenedAt: string; label: string; caseId: number;
  sendAfter: number; state: "saved" | "sent" | "failed"; sentAt?: string; error?: string;
};

const KEY = "rs-outbox";
const UNDO_MS = 10_000;
let listeners: (() => void)[] = [];

function read(): Tap[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; }
}
function write(taps: Tap[]) {
  try { localStorage.setItem(KEY, JSON.stringify(taps.slice(-50))); } catch { /* storage full or blocked */ }
  listeners.forEach((l) => l());
}

export function taps(): Tap[] { return read(); }
export function subscribe(l: () => void) { listeners.push(l); return () => { listeners = listeners.filter((x) => x !== l); }; }

export function tap(t: { url: string; body?: Record<string, unknown>; label: string; caseId: number; undo?: boolean }): string {
  const id = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  write([...read(), { id, url: t.url, body: t.body ?? {}, label: t.label, caseId: t.caseId, happenedAt: new Date().toISOString(),
                      sendAfter: Date.now() + (t.undo === false ? 0 : UNDO_MS), state: "saved" }]);
  flush();
  return id;
}

export function undo(id: string): boolean {
  const all = read();
  const t = all.find((x) => x.id === id);
  if (!t || t.state !== "saved" || Date.now() >= t.sendAfter) return false;
  write(all.filter((x) => x.id !== id));
  return true;
}

let flushing = false;
export async function flush() {
  if (flushing) return;
  flushing = true;
  try {
    for (const t of read().filter((x) => x.state === "saved" && x.sendAfter <= Date.now())) {
      try {
        const r = await fetch(t.url, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": t.id },
                                       body: JSON.stringify({ ...t.body, happened_at: t.happenedAt }) });
        const all = read();
        const i = all.findIndex((x) => x.id === t.id);
        if (i < 0) continue;
        if (r.ok) all[i] = { ...all[i], state: "sent", sentAt: new Date().toISOString() };
        else if (r.status >= 400 && r.status < 500) {
          const body = await r.json().catch(() => ({}));
          all[i] = { ...all[i], state: "failed", error: typeof body.detail === "string" ? body.detail : `refused (${r.status})` };
        }
        write(all);
      } catch { /* offline: stays "saved on phone" and is retried */ }
    }
  } finally { flushing = false; }
}

if (typeof window !== "undefined") {
  setInterval(flush, 1000);
  window.addEventListener("online", () => flush());
}
