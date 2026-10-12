"use client";

// The reporter PWA (PRD F-L2): one big button, tap once to talk. No login, no install, nothing to remember.
// The reply is a fixed sentence (never generated text); the case id is shown only after the server confirms.

import { useEffect, useRef, useState } from "react";
import { deviceId, newId } from "@/lib/device";
import { canRecord, record, type RecorderHandle } from "@/lib/recorder";

type Reply = { hi: string; latin: string; en: string };
type State =
  | { kind: "idle" }
  | { kind: "no-mic" }
  | { kind: "listening"; level: number; seconds: number }
  | { kind: "sending" }
  | { kind: "registered"; publicId: string; reply: Reply }
  | { kind: "processing"; reportId: number }
  | { kind: "empty" }
  | { kind: "not-sent"; retry: () => void }
  | { kind: "busy" }
  | { kind: "typing" };

export default function ReporterPage() {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [incident, setIncident] = useState("BR");
  const handle = useRef<RecorderHandle | null>(null);

  useEffect(() => {
    const i = new URLSearchParams(window.location.search).get("i");
    if (i && /^[A-Z]{2,4}$/.test(i)) setIncident(i);
    if (!canRecord()) setState({ kind: "no-mic" });
  }, []);

  async function send(body: FormData | string, path: string) {
    setState({ kind: "sending" });
    const attempt = async () => {
      try {
        const res = await fetch(path, body instanceof FormData ? { method: "POST", body }
          : { method: "POST", body, headers: { "Content-Type": "application/json" } });
        if (res.status === 422) return setState({ kind: "empty" });
        if (res.status === 429) return setState({ kind: "busy" });
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        if (data.public_id) return registered(data.public_id, data.reply);
        setState({ kind: "processing", reportId: data.report_id });
        poll(data.report_id, data.reply);
      } catch {
        setState({ kind: "not-sent", retry: attempt });
      }
    };
    await attempt();
  }

  function poll(reportId: number, reply: Reply) {
    let tries = 0;
    const timer = setInterval(async () => {
      tries += 1;
      try {
        const r = await fetch(`/v1/public/turns/${reportId}?device_id=${encodeURIComponent(deviceId())}`);
        const d = await r.json();
        if (d.public_id) {
          clearInterval(timer);
          registered(d.public_id, reply);
        }
      } catch { /* keep trying */ }
      if (tries > 30) clearInterval(timer);
    }, 1000);
  }

  function registered(publicId: string, reply: Reply) {
    setState({ kind: "registered", publicId, reply });
    const clip = new Audio("/audio/hi/registered.mp3");   // the team's recorded sentence, if it exists
    clip.play().catch(() => {});
  }

  async function toggle() {
    if (state.kind === "listening") {
      handle.current?.stop();
      return;
    }
    try {
      const { handle: h, done } = await record((level, seconds) => setState({ kind: "listening", level, seconds }));
      handle.current = h;
      setState({ kind: "listening", level: 0, seconds: 0 });
      const clip = await done;
      const form = new FormData();
      form.append("audio", clip.blob, "clip");
      form.append("device_id", deviceId());
      form.append("session_id", newId());
      form.append("incident", incident);
      await send(form, "/v1/public/voice-turns");
    } catch {
      setState({ kind: "no-mic" });
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col px-6 pb-10 pt-8" lang="hi">
      <header className="mb-8">
        <p className="text-sm font-medium tracking-wide text-neutral-500">RakshaSetu</p>
        <h1 className="mt-1 text-2xl font-semibold leading-snug">
          मदद के लिए बताइए
          <span className="block text-lg font-normal text-neutral-600" lang="en">Tell us who needs help, and where</span>
        </h1>
      </header>

      <section aria-live="polite" className="flex flex-1 flex-col items-center justify-center text-center">
        {state.kind === "registered" ? (
          <Registered publicId={state.publicId} reply={state.reply} onAgain={() => setState({ kind: "idle" })} />
        ) : state.kind === "typing" ? (
          <TypeInstead incident={incident} onSend={(t) => send(JSON.stringify({ device_id: deviceId(), session_id: newId(), incident, text: t }), "/v1/public/text-turns")} />
        ) : (
          <>
            <MicButton state={state} onTap={toggle} />
            <StatusLine state={state} />
          </>
        )}
      </section>

      {state.kind !== "registered" && state.kind !== "typing" && (
        <footer className="mt-8 flex flex-col items-center gap-3 text-sm text-neutral-600">
          <button className="underline underline-offset-4" onClick={() => setState({ kind: "typing" })}>
            टाइप करें · Type instead
          </button>
          <p lang="en">If someone is in danger right now, also call <b>112</b> or <b>1077</b>.</p>
        </footer>
      )}
    </main>
  );
}

function MicButton({ state, onTap }: { state: State; onTap: () => void }) {
  const listening = state.kind === "listening";
  const disabled = state.kind === "sending" || state.kind === "processing" || state.kind === "no-mic";
  const level = listening ? state.level : 0;
  return (
    <button
      onClick={onTap}
      disabled={disabled}
      aria-label={listening ? "Stop" : "Tap to talk"}
      className="relative grid size-48 place-items-center rounded-full bg-neutral-950 text-white shadow-sm transition active:scale-95 disabled:bg-neutral-300"
    >
      {listening && (
        <span aria-hidden className="absolute inset-0 rounded-full border-4 border-neutral-950"
          style={{ transform: `scale(${1.06 + level * 0.25})`, opacity: 0.35 + level * 0.5, transition: "transform 80ms linear" }} />
      )}
      {listening ? (
        <span className="block size-12 rounded-md bg-white" />
      ) : (
        <svg viewBox="0 0 24 24" className="size-16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" strokeLinecap="round" />
        </svg>
      )}
    </button>
  );
}

function StatusLine({ state }: { state: State }) {
  const big = "mt-6 text-xl font-medium";
  switch (state.kind) {
    case "idle":
      return <p className={big}>बोलने के लिए दबाएँ<span className="block text-base font-normal text-neutral-600" lang="en">Tap once and speak</span></p>;
    case "listening":
      return <p className={big}>सुन रहे हैं… <span className="tabular">{Math.floor(state.seconds)}s</span><span className="block text-base font-normal text-neutral-600" lang="en">Listening. Tap to stop, or just pause.</span></p>;
    case "sending":
    case "processing":
      return <p className={big}>भेज रहे हैं…<span className="block text-base font-normal text-neutral-600" lang="en">Sending</span></p>;
    case "empty":
      return <p className={big}>कुछ सुनाई नहीं दिया, फिर से कोशिश करें<span className="block text-base font-normal text-neutral-600" lang="en">Didn't hear anything, try again</span></p>;
    case "busy":
      return <p className={big} lang="en">Please wait a moment and try again.</p>;
    case "not-sent":
      return (
        <div className="mt-6">
          <p className="text-xl font-medium text-amber-700">अभी नहीं भेजा गया<span className="block text-base font-normal" lang="en">Not sent yet. If urgent, call 112 / 1077.</span></p>
          <button className="mt-4 rounded-full border border-neutral-900 px-6 py-3 font-medium" onClick={state.retry}>फिर भेजें · Send again</button>
        </div>
      );
    case "no-mic":
      return <p className={big} lang="en">This browser can't use the microphone. Open this page in Chrome, or type instead.</p>;
    default:
      return null;
  }
}

function Registered({ publicId, reply, onAgain }: { publicId: string; reply: Reply; onAgain: () => void }) {
  const [phone, setPhone] = useState("");
  const [saved, setSaved] = useState<"no" | "yes" | "skip">("no");
  async function save() {
    const r = await fetch(`/v1/public/cases/${publicId}/callback`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId(), phone }),
    });
    setSaved(r.ok ? "yes" : "no");
  }
  return (
    <div className="w-full">
      <p className="text-sm font-medium uppercase tracking-wider text-neutral-500">दर्ज हो गई · Registered</p>
      <p className="tabular mt-2 text-6xl font-semibold tracking-tight">{publicId}</p>
      <p className="mt-6 text-lg leading-relaxed">{reply.hi}</p>
      <p className="mt-1 text-neutral-600" lang="en">{reply.en}</p>
      <a href={`/s/${publicId}`} className="mt-6 inline-block rounded-full bg-neutral-950 px-6 py-3 font-medium text-white">स्थिति देखें · See status</a>
      <div className="mt-10 border-t border-neutral-200 pt-6 text-left">
        {saved === "yes" ? (
          <p className="text-neutral-700" lang="en">Thank you. We'll only use it to call you back.</p>
        ) : saved === "skip" ? null : (
          <>
            <label className="block text-sm text-neutral-700" lang="en" htmlFor="cb">A number we can call back? <span className="text-neutral-500">(optional)</span></label>
            <div className="mt-2 flex gap-2">
              <input id="cb" inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                className="tabular min-w-0 flex-1 rounded-xl border border-neutral-300 px-4 py-3 text-lg" placeholder="98xxxxxxxx" />
              <button onClick={save} disabled={phone.length < 10} className="rounded-xl bg-neutral-950 px-4 font-medium text-white disabled:bg-neutral-300">Save</button>
            </div>
            <button onClick={() => setSaved("skip")} className="mt-3 text-sm text-neutral-500 underline underline-offset-4">Skip</button>
          </>
        )}
      </div>
      <button onClick={onAgain} className="mt-8 text-sm text-neutral-600 underline underline-offset-4">एक और रिपोर्ट · Report another</button>
    </div>
  );
}

function TypeInstead({ onSend }: { incident: string; onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  return (
    <div className="w-full text-left">
      <label htmlFor="t" className="block text-lg font-medium">लिखिए · Type it</label>
      <p className="mt-1 text-sm text-neutral-600" lang="en">Who is stuck, how many people, the village, and anything nearby (a temple, a bridge, a school).</p>
      <textarea id="t" value={text} onChange={(e) => setText(e.target.value)} rows={5}
        className="mt-3 w-full rounded-2xl border border-neutral-300 p-4 text-lg" />
      <button onClick={() => onSend(text)} disabled={text.trim().length < 2}
        className="mt-4 w-full rounded-full bg-neutral-950 py-4 text-lg font-medium text-white disabled:bg-neutral-300">भेजें · Send</button>
    </div>
  );
}
