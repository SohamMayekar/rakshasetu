"use client";

// The reporter's "saved on the phone" box. A request for help is written to the phone first when there is no
// signal, and sent by itself the moment there is. The report's own id (session_id) is its idempotency key, so a
// retry, or the same report arriving by two routes, is counted once. Voice clips are kept as they were recorded.
// IndexedDB holds the clips (localStorage is too small); if the browser refuses it, the caller falls back to
// "Send again".

export type Pending = {
  id: string;                       // = session_id, the idempotency key
  kind: "voice" | "text";
  deviceId: string;
  incident: string | null;
  phone: string | null;
  writtenAt: string;                // when the person actually asked, shown to the desk
  text?: string;
  audio?: Blob;
};

export type Delivered = { id: string; reportId: number; publicId: string | null; reply: { en: string } };

const DB = "rakshasetu-reporter";
const STORE = "pending";
let listeners: ((d: Delivered) => void)[] = [];

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") return reject(new Error("no indexedDB"));
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: "id" });
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, run: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = run(db.transaction(STORE, mode).objectStore(STORE));
    req.onsuccess = () => { resolve(req.result); db.close(); };
    req.onerror = () => { reject(req.error); db.close(); };
  });
}

export const put = (p: Pending) => tx("readwrite", (s) => s.put(p));
export const remove = (id: string) => tx("readwrite", (s) => s.delete(id));
export const all = () => tx<Pending[]>("readonly", (s) => s.getAll());

export function onDelivered(l: (d: Delivered) => void): () => void {
  listeners.push(l);
  return () => { listeners = listeners.filter((x) => x !== l); };
}

export type Outcome =
  | { status: "ok"; data: { report_id: number; public_id: string | null; reply: { en: string } } }
  | { status: "rejected"; code: "empty" | "bad_audio" | "busy" | "too_big" | "other" }
  | { status: "offline" };

/** One attempt to hand a pending report to the server. Never throws. */
export async function deliver(p: Pending): Promise<Outcome> {
  try {
    let res: Response;
    if (p.kind === "voice" && p.audio) {
      const form = new FormData();
      form.append("audio", p.audio, "clip");
      form.append("device_id", p.deviceId);
      form.append("session_id", p.id);
      form.append("written_at", p.writtenAt);
      if (p.incident) form.append("incident", p.incident);
      if (p.phone) form.append("phone", p.phone);
      res = await fetch("/v1/public/voice-turns", { method: "POST", body: form });
    } else {
      res = await fetch("/v1/public/text-turns", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: p.deviceId, session_id: p.id, incident: p.incident, text: p.text ?? "",
                               phone: p.phone, written_at: p.writtenAt }),
      });
    }
    if (res.ok) return { status: "ok", data: await res.json() };
    if (res.status === 429) return { status: "rejected", code: "busy" };
    if (res.status === 413) return { status: "rejected", code: "too_big" };
    if (res.status === 422) {
      const body = await res.json().catch(() => ({}));
      const code = body?.detail?.code;
      return { status: "rejected", code: code === "bad_audio" ? "bad_audio" : "empty" };
    }
    if (res.status >= 500 || res.status === 408) return { status: "offline" };   // the server's trouble: keep it, try again
    return { status: "rejected", code: "other" };
  } catch {
    return { status: "offline" };   // no signal, a dropped connection, a tunnel that is down
  }
}

let flushing = false;
/** Send everything kept on the phone. Called when the signal returns and on a slow timer while anything waits. */
export async function flush(): Promise<void> {
  if (flushing || (typeof navigator !== "undefined" && navigator.onLine === false)) return;
  flushing = true;
  try {
    for (const p of await all().catch(() => [] as Pending[])) {
      const out = await deliver(p);
      if (out.status === "offline") break;   // still no way through: keep the rest, stop hammering
      if (out.status === "rejected" && out.code === "busy") break;
      await remove(p.id).catch(() => {});
      if (out.status === "ok") listeners.forEach((l) => l({ id: p.id, reportId: out.data.report_id, publicId: out.data.public_id, reply: out.data.reply }));
    }
  } finally { flushing = false; }
}

if (typeof window !== "undefined") {
  window.addEventListener("online", () => void flush());
  setInterval(() => void flush(), 8000);
}
