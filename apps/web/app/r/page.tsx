"use client";

// The reporter PWA (PRD F-L2): one big microphone button, one text box, one Send button. No login, no install, no
// code, nothing to remember. The reply is a fixed sentence (never generated text); the case number is shown after
// the server confirms, to show a rescuer if they like, never to type or remember.
//
// A call-back number sits right there, optional, and travels with the report (voice or text). With no signal the
// request is kept on the phone and sent by itself when there is signal (lib/reportBox), and it can be handed to
// someone nearby to forward. Nothing here ever blocks a request for help: a mistyped number is simply left out.

import { CheckCheck, Mic, Phone, Share2, WifiOff } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Mark } from "@/components/shell/Sidebar";
import { deviceId, newId } from "@/lib/device";
import { canRecord, micProblem, type MicProblem, record, type RecorderHandle } from "@/lib/recorder";
import { deliver, flush, onDelivered, type Pending, put } from "@/lib/reportBox";

type Reply = { en: string };
type State =
  | { kind: "idle" }
  | { kind: "no-mic"; why: MicProblem }
  | { kind: "listening"; level: number; seconds: number }
  | { kind: "sending" }
  | { kind: "registered"; publicId: string; reply: Reply }
  | { kind: "processing"; reportId: number }
  | { kind: "received"; reply: Reply }                 // accepted, the case is still being made: nothing is lost
  | { kind: "kept"; share: string }                    // saved on the phone, will send itself
  | { kind: "problem"; text: string; again: boolean }; // a clear sentence; "again" offers the mic once more

const PHONE_KEY = "rakshasetu.callback";
const digitsOf = (v: string) => v.replace(/\D/g, "");
/** A 10-digit Indian mobile number (with or without +91 / 0), or null. Matches the server's rule. */
function cleanPhone(v: string): string | null {
  let d = digitsOf(v);
  if (d.startsWith("0091")) d = d.slice(4);
  else if (d.length === 12 && d.startsWith("91")) d = d.slice(2);
  else if (d.length === 11 && d.startsWith("0")) d = d.slice(1);
  return d.length === 10 && "6789".includes(d[0]) ? d : null;
}

export default function ReporterPage() {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [incident, setIncident] = useState<string | null>(null);   // none: the API files it under the live incident
  const [phone, setPhone] = useState("");
  const [text, setText] = useState("");
  const [online, setOnline] = useState(true);
  const handle = useRef<RecorderHandle | null>(null);
  const starting = useRef(false);
  const phoneRef = useRef("");
  phoneRef.current = phone;

  useEffect(() => {
    const i = new URLSearchParams(window.location.search).get("i");
    if (i && /^[A-Z]{2,4}$/.test(i)) setIncident(i);
    if (!canRecord()) setState({ kind: "no-mic", why: "unsupported" });
    try { setPhone(localStorage.getItem(PHONE_KEY) ?? ""); } catch { /* blocked storage: the field just starts empty */ }
    setOnline(navigator.onLine);
    const on = () => { setOnline(true); void flush(); };
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  const poll = useCallback((reportId: number, reply: Reply) => {
    let tries = 0;
    const timer = setInterval(async () => {
      tries += 1;
      try {
        const r = await fetch(`/v1/public/turns/${reportId}?device_id=${encodeURIComponent(deviceId())}`);
        const d = await r.json();
        if (d.public_id) { clearInterval(timer); registered(d.public_id, reply); return; }
      } catch { /* keep trying */ }
      if (tries >= 40) { clearInterval(timer); setState({ kind: "received", reply }); }   // accepted; being read
    }, 1500);
  }, []);

  function registered(publicId: string, reply: Reply) {
    setState({ kind: "registered", publicId, reply });
    try { navigator.vibrate?.([40, 60, 40]); } catch { /* not everywhere */ }
    new Audio("/audio/en/registered.mp3").play().catch(() => {});   // the team's recorded sentence, if it exists
  }

  // A report that waited on the phone and has now gone through.
  useEffect(() => onDelivered((d) => {
    if (d.publicId) registered(d.publicId, d.reply);
    else { setState({ kind: "processing", reportId: d.reportId }); poll(d.reportId, d.reply); }
  }), [poll]);

  const shareText = (body: string) => `Need help. ${body}${cleanPhone(phoneRef.current) ? ` Call me: ${cleanPhone(phoneRef.current)}.` : ""}`;

  async function submit(p: Pending, share: string) {
    setState({ kind: "sending" });
    try { localStorage.setItem(PHONE_KEY, phoneRef.current); } catch { /* ignore */ }
    const out = await deliver(p);
    if (out.status === "ok") {
      if (out.data.public_id) return registered(out.data.public_id, out.data.reply);
      setState({ kind: "processing", reportId: out.data.report_id });
      return poll(out.data.report_id, out.data.reply);
    }
    if (out.status === "offline") {
      try { await put(p); setState({ kind: "kept", share }); }
      catch { setState({ kind: "problem", again: false, text: "Not sent yet. If it is urgent, call 112 or 1077." }); }
      return;
    }
    const why = {
      empty: "We didn’t hear anything. Please try again, or write it below.",
      bad_audio: "We couldn’t play that recording. Please try again, or write it below.",
      busy: "Lots of people are asking at once. Please wait a moment and try again.",
      too_big: "That recording was too long. Please try a shorter one, or write it below.",
      other: "That didn’t go through. Please try again. If it is urgent, call 112 or 1077.",
    }[out.code];
    setState({ kind: "problem", text: why, again: out.code !== "busy" });
  }

  const base = (): Pending => ({ id: newId(), kind: "text", deviceId: deviceId(), incident, phone: cleanPhone(phoneRef.current),
                                 writtenAt: new Date().toISOString() });

  async function toggle() {
    if (state.kind === "listening") { handle.current?.stop(); return; }
    if (starting.current) return;       // a second tap while the browser asks for the microphone
    starting.current = true;
    let rec: Awaited<ReturnType<typeof record>>;
    try {
      rec = await record((level, seconds) => setState({ kind: "listening", level, seconds }));
    } catch (e) {
      starting.current = false;
      return setState({ kind: "no-mic", why: micProblem(e) });
    }
    starting.current = false;
    handle.current = rec.handle;
    setState({ kind: "listening", level: 0, seconds: 0 });
    try { navigator.vibrate?.(30); } catch { /* ignore */ }
    const clip = await rec.done;
    if (clip.blob.size < 500) return setState({ kind: "problem", again: true, text: "We didn’t hear anything. Please try again, or write it below." });
    await submit({ ...base(), kind: "voice", audio: clip.blob }, "Need help. (voice message)");
  }

  const sendText = () => {
    const t = text.trim();
    if (t.length < 2) return;
    void submit({ ...base(), kind: "text", text: t }, shareText(t));
  };

  const busy = state.kind === "sending" || state.kind === "processing" || state.kind === "listening";
  const phoneBad = phone.trim() !== "" && !cleanPhone(phone);
  const done = state.kind === "registered" || state.kind === "received";

  return (
    <main className="safe-page mx-auto flex min-h-dvh max-w-md flex-col gap-3 bg-canvas px-4">
      <header className="flex items-center justify-between">
        <p className="flex items-center gap-2 text-body font-semibold text-ink"><Mark className="size-6" />RakshaSetu</p>
        <a href="tel:112" className="inline-flex h-9 items-center gap-1.5 rounded-full border border-line bg-paper px-3 text-small font-semibold shadow-[var(--shadow-card)]">
          <Phone className="size-3.5" aria-hidden />Call 112
        </a>
      </header>

      {!online && !done && (
        <p role="status" className="flex items-start gap-3 rounded-2xl bg-ink px-4 py-3 text-body text-paper">
          <WifiOff className="mt-0.5 size-5 shrink-0" aria-hidden />
          <span>No signal. You can still record or write. It is saved on your phone and sent by itself when you are back online.</span>
        </p>
      )}

      {!done && state.kind !== "kept" && (
        <div className="px-1 pt-2">
          <h1 className="text-display font-semibold leading-tight tracking-tight">Need help?</h1>
          <p className="mt-1 text-body text-ink-2">Tell us what is happening, in your own language. A team is sent, and we follow it until you are safe.</p>
        </div>
      )}

      <section aria-live="polite" className="rounded-card border border-line/70 bg-paper px-5 py-6 text-center shadow-[var(--shadow-card)]">
        {state.kind === "registered" || state.kind === "received" ? (
          <Registered publicId={state.kind === "registered" ? state.publicId : null} reply={state.reply} given={cleanPhone(phone)}
                      onAgain={() => { setText(""); setState({ kind: "idle" }); }} />
        ) : state.kind === "kept" ? (
          <Kept share={state.share} onAgain={() => { setText(""); setState({ kind: "idle" }); }} />
        ) : (
          <>
            <MicButton state={state} onTap={toggle} />
            <StatusLine state={state} />
            {state.kind === "idle" && (
              <ul className="mt-4 flex flex-wrap justify-center gap-1.5 text-small text-ink-2" aria-label="What to say">
                {["How many people", "Which village", "What is near you", "Anyone hurt or elderly"].map((t) => (
                  <li key={t} className="rounded-full bg-wash px-3 py-1">{t}</li>
                ))}
              </ul>
            )}

            <div className="my-5 flex items-center gap-3 text-micro font-semibold uppercase tracking-[0.14em] text-ink-3">
              <span className="h-px flex-1 bg-line" />or write it<span className="h-px flex-1 bg-line" />
            </div>

            <label htmlFor="t" className="block text-left text-body font-medium">What is happening?</label>
            <textarea id="t" value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={2000} disabled={busy}
                      placeholder="Six people are trapped in the house behind the primary school on Station Road. An old man needs medicine."
                      className="field-lg mt-2 leading-snug" />

            <label htmlFor="cb" className="mt-4 block text-left text-body font-medium">
              A number to call you back <span className="font-normal text-ink-3">(optional)</span>
            </label>
            <div className={`mt-2 flex items-center overflow-hidden rounded-2xl border bg-paper transition-[border-color,box-shadow] focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgb(21_21_21/.08)] ${phoneBad ? "border-p1" : "border-line"}`}>
              <span className="select-none border-r border-line px-3 py-3 text-lg text-ink-2">+91</span>
              <input id="cb" type="tel" inputMode="tel" autoComplete="tel-national" value={phone} maxLength={20}
                     onChange={(e) => setPhone(e.target.value)} disabled={busy} placeholder="98765 43210"
                     className="tabular min-w-0 flex-1 bg-transparent px-3 py-3 text-lg outline-none" />
            </div>
            <p className={`mt-1.5 text-left text-small ${phoneBad ? "text-p1" : "text-ink-3"}`}>
              {phoneBad ? "That doesn’t look like a 10-digit mobile number. We will send your request without it."
                : "Only used so a rescuer can call you. It is never shown to the public."}
            </p>

            <button onClick={sendText} disabled={busy || text.trim().length < 2}
                    className="mt-4 w-full rounded-full bg-ink py-4 text-lg font-medium text-paper transition active:scale-[.99] disabled:bg-ink-3">
              Send
            </button>
          </>
        )}
      </section>

      {!done && state.kind !== "kept" && (
        <>
          <ol className="grid grid-cols-3 gap-2 text-center text-small text-ink-2" aria-label="What happens next">
            {["You ask for help", "One team is sent", "You confirm you are safe"].map((s, i) => (
              <li key={s} className="rounded-2xl bg-paper/70 px-2 py-3 shadow-[var(--shadow-card)]">
                <span className="mx-auto mb-1 grid size-6 place-items-center rounded-full bg-ink text-micro font-semibold text-paper">{i + 1}</span>{s}
              </li>
            ))}
          </ol>
          <p className="flex items-center gap-3 rounded-2xl bg-paper px-4 py-3 text-body text-ink-2 shadow-[var(--shadow-card)]">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-wash"><Phone className="size-4" aria-hidden /></span>
            <span>If someone is in danger right now, also call <a href="tel:112" className="font-semibold text-ink underline">112</a> or <a href="tel:1077" className="font-semibold text-ink underline">1077</a>.</span>
          </p>
          <p className="text-center text-small text-ink-3">
            No signal? <a href="/mesh" className="underline underline-offset-4">See how a request still gets through</a>.
          </p>
        </>
      )}
    </main>
  );
}

function MicButton({ state, onTap }: { state: State; onTap: () => void }) {
  const listening = state.kind === "listening";
  const disabled = state.kind === "sending" || state.kind === "processing" || (state.kind === "no-mic");
  const level = listening ? state.level : 0;
  return (
    <button onClick={onTap} disabled={disabled} aria-label={listening ? "Stop recording" : "Tap to talk"}
            className="relative mx-auto grid size-36 place-items-center rounded-full bg-ink text-paper shadow-[0_8px_30px_rgba(21,21,21,0.25)] ring-8 ring-wash transition active:scale-95 disabled:bg-ink-3 disabled:shadow-none">
      {listening && (
        <span aria-hidden className="absolute inset-0 rounded-full border-4 border-ink"
              style={{ transform: `scale(${1.06 + level * 0.3})`, opacity: 0.35 + level * 0.5, transition: "transform 80ms linear" }} />
      )}
      {!listening && state.kind === "idle" && <span aria-hidden className="lp-ping absolute inset-0 rounded-full border-2 border-ink/40" />}
      {listening ? <span className="block size-11 rounded-md bg-white" /> : <Mic className="size-14" strokeWidth={1.7} aria-hidden />}
    </button>
  );
}

function StatusLine({ state }: { state: State }) {
  const big = "mt-4 text-xl font-medium";
  switch (state.kind) {
    case "idle":
      return <p className={big}>Tap and speak</p>;
    case "listening":
      return <p className={big}>Listening… <span className="tabular">{Math.floor(state.seconds)}s</span>
        <span className="block text-base font-normal text-ink-2">Tap to stop, or pause for a moment.</span></p>;
    case "sending":
    case "processing":
      return <p className={big}>Sending…<span className="block text-base font-normal text-ink-2">Please keep this page open.</span></p>;
    case "problem":
      return <p className={`${big} text-ink`}>{state.text}</p>;
    case "no-mic": {
      const msg = {
        denied: "The microphone is blocked. Allow it in your browser’s settings, or write below.",
        none: "No microphone was found on this phone. Please write below.",
        busy: "Another app is using the microphone. Close it and tap again, or write below.",
        unsupported: "This browser can’t record. Open this page in Chrome, or write below.",
      }[state.why];
      return <p className={big}>{msg}</p>;
    }
    default:
      return null;
  }
}

// Asked for help with no signal: it is on the phone, and it can be handed to someone nearby right now.
function Kept({ share, onAgain }: { share: string; onAgain: () => void }) {
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";
  return (
    <div className="w-full text-left">
      <span className="grid size-12 place-items-center rounded-full bg-ink text-paper"><WifiOff className="size-6" aria-hidden /></span>
      <p className="mt-4 text-display font-semibold leading-tight tracking-tight">Saved on your phone.</p>
      <p className="mt-2 text-lg leading-relaxed text-ink-2">There is no signal right now. Keep this page open or come back to it: it will be sent by itself the moment you have signal.</p>
      <div className="mt-5 rounded-2xl bg-wash p-4">
        <p className="text-body font-medium">Someone nearby with signal?</p>
        <p className="mt-0.5 text-small text-ink-2">Hand them the message. Any message sent to the desk, from WhatsApp or SMS, is read the same way.</p>
        {canShare ? (
          <button onClick={() => navigator.share({ title: "Need help", text: share }).catch(() => {})}
                  className="mt-3 inline-flex h-11 items-center gap-2 rounded-full bg-ink px-5 font-medium text-paper">
            <Share2 className="size-4" aria-hidden />Pass it on
          </button>
        ) : (
          <p className="mt-3 rounded-xl bg-paper p-3 text-body select-all">{share}</p>
        )}
      </div>
      <p className="mt-4 text-small text-ink-3">If it is urgent, call <a href="tel:112" className="underline">112</a> or <a href="tel:1077" className="underline">1077</a> as soon as you can.</p>
      <button onClick={onAgain} className="mt-3 min-h-11 text-body text-ink-2 underline underline-offset-4">Write another</button>
    </div>
  );
}

function Registered({ publicId, reply, given, onAgain }: { publicId: string | null; reply: Reply; given: string | null; onAgain: () => void }) {
  const [phone, setPhone] = useState("");
  const [saved, setSaved] = useState<"no" | "yes" | "skip">("no");
  const [asking, setAsking] = useState(false);
  const mine = cleanPhone(phone);
  async function save() {
    if (!publicId || !mine) return;
    const r = await fetch(`/v1/public/cases/${publicId}/callback`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId(), phone: mine }),
    }).catch(() => null);
    setSaved(r?.ok ? "yes" : "no");
  }
  return (
    <div className="w-full">
      <span className="mx-auto grid size-14 place-items-center rounded-full bg-ink text-paper"><CheckCheck className="size-7" aria-hidden /></span>
      <p className="mt-4 text-display font-semibold leading-tight tracking-tight">We have your report.</p>
      <p className="mt-3 text-lg leading-relaxed text-ink-2">{publicId ? reply.en : "It is safely with the desk and is being read now. You don’t need to do anything else."}</p>
      {publicId && <p className="mt-5 text-body text-ink-3">Your case number is <span className="tabular font-semibold text-ink">{publicId}</span>, in case a rescuer asks. You don&rsquo;t need to remember it.</p>}
      {publicId && <a href={`/s/${publicId}`} className="mt-5 inline-block rounded-full bg-ink px-6 py-3 font-medium text-paper">See what happens next</a>}
      {publicId && (
        <div className="mt-8 border-t border-line pt-5 text-left">
          {given ? (
            <p className="text-ink-2">A rescuer can call you on <span className="tabular font-semibold text-ink">+91 {given.slice(0, 2)}xxxxxx{given.slice(-2)}</span>. We will only use it for that.</p>
          ) : saved === "yes" ? (
            <p className="text-ink-2">Thank you. We&apos;ll only use it to call you back.</p>
          ) : saved === "skip" || !asking ? (
            <button onClick={() => setAsking(true)} className="min-h-11 text-body text-ink-2 underline underline-offset-4">Want a call back? Add a number (optional)</button>
          ) : (
            <>
              <label className="block text-body text-ink-2" htmlFor="cb2">A number we can call back <span className="text-ink-3">(optional)</span></label>
              <div className="mt-2 flex gap-2">
                <input id="cb2" type="tel" inputMode="tel" autoComplete="tel-national" value={phone} onChange={(e) => setPhone(e.target.value)}
                       className="tabular min-w-0 flex-1 rounded-xl border border-line px-4 py-3 text-lg" placeholder="98765 43210" />
                <button onClick={save} disabled={!mine} className="rounded-xl bg-ink px-4 font-medium text-paper disabled:bg-ink-3">Save</button>
              </div>
              {saved === "no" && phone !== "" && mine && <p className="mt-1 text-small text-ink-3">Couldn’t save it just now. You can try again.</p>}
              <button onClick={() => setSaved("skip")} className="mt-1 min-h-11 text-body text-ink-3 underline underline-offset-4">No thanks</button>
            </>
          )}
        </div>
      )}
      <button onClick={onAgain} className="mt-4 min-h-11 text-body text-ink-2 underline underline-offset-4">Report another family</button>
    </div>
  );
}
