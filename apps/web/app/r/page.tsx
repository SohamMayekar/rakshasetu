"use client";

// The reporter PWA (PRD F-L2): one big microphone button, one text box, one Send button (m70). No login, no
// install, no code, nothing to remember. The reply is a fixed sentence (never generated text); the case number is
// shown after the server confirms, to show a rescuer if they like, never to type or remember. The call-back
// number is optional and folded away.

import { Phone } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Mark } from "@/components/shell/Sidebar";
import { deviceId, newId } from "@/lib/device";
import { canRecord, record, type RecorderHandle } from "@/lib/recorder";

type Reply = { en: string };
type State =
  | { kind: "idle" }
  | { kind: "no-mic" }
  | { kind: "listening"; level: number; seconds: number }
  | { kind: "sending" }
  | { kind: "registered"; publicId: string; reply: Reply }
  | { kind: "processing"; reportId: number }
  | { kind: "empty" }
  | { kind: "not-sent"; retry: () => void }
  | { kind: "busy" };

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
    const clip = new Audio("/audio/en/registered.mp3");   // the team's recorded sentence, if it exists
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
    <main className="mx-auto flex min-h-dvh max-w-md flex-col bg-canvas px-5 pb-8 pt-6">
      <header className="mb-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-ink"><Mark className="size-6" />RakshaSetu</p>
        <h1 className="mt-4 text-[26px] font-semibold leading-tight tracking-tight">Tell us who needs help, and where</h1>
      </header>

      <section aria-live="polite" className="flex flex-1 flex-col items-center justify-center rounded-[28px] bg-paper px-5 py-8 text-center shadow-[var(--shadow-card)]">
        {state.kind === "registered" ? (
          <Registered publicId={state.publicId} reply={state.reply} onAgain={() => setState({ kind: "idle" })} />
        ) : (
          <>
            <MicButton state={state} onTap={toggle} />
            <StatusLine state={state} />
            <TypeIt disabled={state.kind === "sending" || state.kind === "processing" || state.kind === "listening"}
                    onSend={(t) => send(JSON.stringify({ device_id: deviceId(), session_id: newId(), incident, text: t }), "/v1/public/text-turns")} />
          </>
        )}
      </section>

      {state.kind !== "registered" && (
        <p className="mt-4 flex items-center gap-3 rounded-2xl bg-paper px-4 py-3 text-sm text-ink-2 shadow-[var(--shadow-card)]">
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-wash"><Phone className="size-4" aria-hidden /></span>
          <span>If someone is in danger right now, also call <b>112</b> or <b>1077</b>.</span>
        </p>
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
      className="relative grid size-40 place-items-center rounded-full bg-ink text-paper shadow-[0_8px_30px_rgba(21,21,21,0.25)] ring-8 ring-wash transition active:scale-95 disabled:bg-ink-3 disabled:shadow-none"
    >
      {listening && (
        <span aria-hidden className="absolute inset-0 rounded-full border-4 border-ink"
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
  const big = "mt-4 text-xl font-medium";
  switch (state.kind) {
    case "idle":
      return <p className={big}>Tap and speak</p>;
    case "listening":
      return <p className={big}>Listening… <span className="tabular">{Math.floor(state.seconds)}s</span><span className="block text-base font-normal text-ink-2">Tap to stop, or just pause.</span></p>;
    case "sending":
    case "processing":
      return <p className={big}>Sending…</p>;
    case "empty":
      return <p className={big}>Didn&rsquo;t hear anything. Please try again.</p>;
    case "busy":
      return <p className={big}>Please wait a moment and try again.</p>;
    case "not-sent":
      return (
        <div className="mt-6">
          <p className="text-xl font-medium text-amber-700">Not sent yet<span className="block text-base font-normal">If urgent, call 112 / 1077.</span></p>
          <button className="mt-4 rounded-full border border-ink px-6 py-3 font-medium" onClick={state.retry}>Send again</button>
        </div>
      );
    case "no-mic":
      return <p className={big}>This browser can&rsquo;t use the microphone. Open this page in Chrome, or type below.</p>;
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
  const [asking, setAsking] = useState(false);
  return (
    <div className="w-full">
      <p className="text-[28px] font-semibold leading-tight tracking-tight">We have your report.</p>
      <p className="mt-3 text-lg leading-relaxed text-ink-2">{reply.en}</p>
      <p className="mt-5 text-sm text-ink-3">Your case number is <span className="tabular font-semibold text-ink">{publicId}</span>, in case a rescuer asks. You don&rsquo;t need to remember it.</p>
      <a href={`/s/${publicId}`} className="mt-5 inline-block rounded-full bg-ink px-6 py-3 font-medium text-paper">See what happens next</a>
      <div className="mt-8 border-t border-line pt-5 text-left">
        {saved === "yes" ? (
          <p className="text-ink-2">Thank you. We&apos;ll only use it to call you back.</p>
        ) : saved === "skip" || !asking ? (
          <button onClick={() => setAsking(true)} className="text-sm text-ink-2 underline underline-offset-4">Want a call back? Add a number (optional)</button>
        ) : (
          <>
            <label className="block text-sm text-ink-2" htmlFor="cb">A number we can call back <span className="text-ink-3">(optional)</span></label>
            <div className="mt-2 flex gap-2">
              <input id="cb" inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                className="tabular min-w-0 flex-1 rounded-xl border border-line px-4 py-3 text-lg" placeholder="98xxxxxxxx" />
              <button onClick={save} disabled={phone.length < 10} className="rounded-xl bg-ink px-4 font-medium text-paper disabled:bg-ink-3">Save</button>
            </div>
            <button onClick={() => setSaved("skip")} className="mt-3 text-sm text-ink-3 underline underline-offset-4">No thanks</button>
          </>
        )}
      </div>
      <button onClick={onAgain} className="mt-6 text-sm text-ink-2 underline underline-offset-4">Report another family</button>
    </div>
  );
}

// The text box is always there, under the microphone: no mode to switch, nothing to find.
function TypeIt({ onSend, disabled }: { onSend: (text: string) => void; disabled: boolean }) {
  const [text, setText] = useState("");
  return (
    <div className="mt-6 w-full text-left">
      <label htmlFor="t" className="block text-sm text-ink-2">Or type: who is stuck, how many people, the village, anything nearby</label>
      <textarea id="t" value={text} onChange={(e) => setText(e.target.value)} rows={3}
        className="mt-2 w-full rounded-2xl border border-line p-3 text-lg" />
      <button onClick={() => onSend(text)} disabled={disabled || text.trim().length < 2}
        className="mt-3 w-full rounded-full bg-ink py-4 text-lg font-medium text-paper disabled:bg-ink-3">Send</button>
    </div>
  );
}
