"use client";

// Demo (PRD F-C12), m71: a numbered walk through the 5-minute story. The current scene in big type with one line of
// what to do, a big "Next scene", the two QR codes and the honesty lines; each scene can be reset to its own
// starting point (local listener only, DEMO_MODE only, Demo admin). AI reading on/off, the recorded clip, the
// partner moment and the surge are under "More controls"; "Show it under load" and "Show a partner system" link out.
// Open it at http://127.0.0.1/demo signed in as Demo admin, and keep the desk on http://localhost: the two
// addresses keep separate sign-ins, so the officer on the projector stays signed in.

import { ArrowRight, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AppShell, Page } from "@/components/shell/AppShell";
import { Button, Card, PageHeader, Section } from "@/components/ui";
import { api, ApiError, type Me } from "@/lib/api";

type Scene = { id: string; at: string; title: string; starts_with: string };
type Status = { demo_mode: boolean; listener: string; public_url: string; language_model: "on" | "off";
                provider_mode: string; keys: { stt: string[]; llm: string[] };
                surge: { rate: number; duration: number; seconds_left: number } | null };
type Clip = { clip: string; synthetic: boolean; bytes: number };
type Reset = { scene: string; seconds: number; son_case: string | null };

const why = (e: unknown) => (e instanceof ApiError ? String((e.detail as string) ?? e.message) : String(e));

export default function DemoPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [clips, setClips] = useState<Clip[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [line, setLine] = useState<string | null>(null);
  const [qrKey, setQrKey] = useState(0);
  const [at, setAt] = useState(0);   // the presenter's place in the story (this browser only)
  useEffect(() => { try { setAt(Number(localStorage.getItem("rs-demo-at") ?? 0) || 0); } catch { /* storage blocked */ } }, []);
  const go = (i: number) => { setAt(i); try { localStorage.setItem("rs-demo-at", String(i)); } catch { /* storage blocked */ } };

  const refresh = useCallback(() => { api<Status>("/v1/demo/status").then(setStatus).catch((e) => setLine(why(e))); }, []);
  useEffect(() => {
    api<Me>("/v1/me").then(setMe).catch(() => setMe(null));
    refresh();
    api<Scene[]>("/v1/demo/scenes").then(setScenes).catch(() => {});
    api<Clip[]>("/v1/demo/clips").then(setClips).catch(() => {});
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [refresh]);

  const run = async (label: string, fn: () => Promise<string>) => {
    setBusy(label); setLine(null);
    try { setLine(await fn()); } catch (e) { setLine(`${label}: ${why(e)}`); } finally { setBusy(null); refresh(); setQrKey((k) => k + 1); }
  };

  if (me && me.user.role !== "admin") {   // the duty officer on the projector: the script and the two "show" pages
    return (
      <AppShell me={me}><Page>
        <PageHeader title="Demo" sub="Run it live: real phones, the real desk." />
        <Shows />
        <Card className="mt-3 px-5 py-4 text-body">
          <ol className="space-y-2">{SCRIPT.map((x, i) => <li key={x.id}><b className="tabular">{i + 1}. {x.title}</b> <span className="text-ink-2">· {x.do}</span></li>)}</ol>
          <p className="mt-3 text-ink-3">The reset buttons and QR codes are for the Demo admin: open <b>http://127.0.0.1/demo</b> and sign in as Demo admin
            there, so this desk on <b>http://localhost</b> stays signed in as {me.user.name}.</p>
        </Card>
      </Page></AppShell>
    );
  }

  const scene = SCRIPT[Math.min(at, SCRIPT.length - 1)];
  const reset = (id: string, title: string) => run(`Reset to ${title}`, async () => {
    const r = await api<Reset>("/v1/demo/reset", { method: "POST", json: { scene: id } });
    return `Reset to “${title}” in ${r.seconds} s${r.son_case ? ` · the son's case is ${r.son_case}` : ""}. Every open screen reloads.`;
  });
  const sonClip = clips[0];
  return (
    <AppShell me={me}>
    <Page>
      <PageHeader title="Demo" sub="Run it live: real phones, the real desk." />
      {line && <p className="mt-4 rounded-xl bg-paper px-4 py-2.5 text-body shadow-[var(--shadow-card)]" role="status">{line}</p>}

      <ol className="mt-6 grid grid-cols-3 gap-2 sm:grid-cols-6" aria-label="Scenes">
        {SCRIPT.map((x, i) => (
          <li key={x.id}>
            <button onClick={() => go(i)} aria-current={i === at ? "step" : undefined}
                    className={`flex h-full w-full flex-col items-start rounded-2xl px-3 py-2.5 text-left text-body ${i === at ? "bg-ink text-paper" : i < at ? "bg-paper text-ink-3" : "bg-paper text-ink"} shadow-[var(--shadow-card)]`}>
              <span className="tabular text-lg font-semibold">{i + 1}</span><span className="leading-tight">{x.title}</span>
            </button>
          </li>
        ))}
      </ol>

      <Card className="mt-4 px-6 py-6">
        <p className="text-body text-ink-3">Step {at + 1} of {SCRIPT.length}</p>
        <h2 className="mt-1 text-display font-semibold leading-tight tracking-tight">{scene.title}</h2>
        <p className="mt-2 text-lg leading-snug">{scene.do}</p>
        <div className="mt-6 flex flex-wrap items-center gap-3">
          {at < SCRIPT.length - 1
            ? <Button variant="primary" className="!h-12 !px-7 !text-base" onClick={() => go(at + 1)}>Next step<ArrowRight className="size-4" aria-hidden /></Button>
            : <Button variant="primary" className="!h-12 !px-7 !text-base" onClick={() => go(0)}>Back to step 1</Button>}
          {scene.id === "son" && sonClip && (
            <Button disabled={!!busy} onClick={() => run("Play the son's clip", async () => {
              const r = await api<{ report_id: number }>("/v1/demo/play-clip", { method: "POST", json: { clip: sonClip.clip } });
              return `Played the son's clip (${sonClip.synthetic ? "a synthetic voice, a recording" : "a recording"}): report ${r.report_id} is being read. Watch the desk.`;
            })}>No phone? Send the recorded clip</Button>
          )}
          {scene.id === "receipts" && <a href="/audit" className="text-body underline underline-offset-4">Open History</a>}
          <Button variant="quiet" disabled={!!busy} onClick={() => reset(scene.id, scene.title)}>
            <RotateCcw className="size-4" aria-hidden />{busy === `Reset to ${scene.title}` ? "Resetting…" : "Start this step again"}</Button>
        </div>
      </Card>

      <div className="mt-4 grid gap-4 md:grid-cols-[1fr_1.2fr]">
        <Card className="px-5 py-4 text-body">
          <p className="font-semibold">Say it once</p>
          <ul className="mt-2 space-y-1.5 text-ink-2">
            <li>People and phone numbers are made up.</li>
            <li>The clock runs 60× faster, so a 15-minute wait takes 15 seconds.</li>
            <li>The partner system is our own, simulated.</li>
            {!status?.keys.stt.length && <li>Without a speech key, voice clips are recordings.</li>}
          </ul>
        </Card>
        <Card className="px-5 py-4 text-body">
          <p className="font-semibold">Phones</p>
          {status && !status.public_url
            ? <p className="mt-2 text-ink-2">Start the tunnel and put its address in <code>PUBLIC_URL</code> (<code>.env</code>): the QR codes appear here.</p>
            : (
              <div className="mt-2 grid gap-4 sm:grid-cols-2">
                <Qr key={`r${qrKey}`} target="reporter" title="Ask for help" note="Any judge's phone: speak or type." />
                <Qr key={`s${qrKey}`} target="son" title="The family's phone" note="Follows the case; asked “Is that right?” after the rescue." />
              </div>
            )}
        </Card>
      </div>

      <details className="mt-4 rounded-card bg-paper px-5 py-3 shadow-[var(--shadow-card)]">
        <summary className="cursor-pointer select-none py-1 text-body font-medium">More controls</summary>
        <div className="text-body">
          <Shows />
          <Box title="Start any scene again">
            <ol className="divide-y divide-line">
              {scenes.map((x, i) => (
                <li key={x.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="min-w-0"><span className="tabular text-ink-3">{i + 1}.</span> <b>{x.title}</b>
                    <span className="block text-ink-2">{x.starts_with}</span></span>
                  <Button size="sm" className="shrink-0 whitespace-nowrap" disabled={!!busy} onClick={() => { go(i); reset(x.id, x.title); }}>
                    {busy === `Reset to ${x.title}` ? "Resetting…" : "Reset here"}</Button>
                </li>
              ))}
            </ol>
          </Box>
          <Box title="AI reading">
            <div className="flex items-center justify-between gap-3">
              <span>
                {status && !status.keys.llm.length
                  ? <>The switch is <b>{status.language_model}</b>, but no AI key is set: fixed word rules read every report either way.</>
                  : <>AI reading is <b>{status?.language_model ?? "…"}</b>{status ? ` (${status.keys.llm.join(", ")})` : ""}. Turn it off to show that cases are still made.</>}
              </span>
              <Button size="sm" className="shrink-0 whitespace-nowrap" disabled={!!busy || !status} onClick={() => run("AI reading", async () => {
                const on = status?.language_model !== "on";
                await api("/v1/demo/language-model", { method: "POST", json: { on } });
                return `AI reading ${on ? "on" : "off"}: typed reports still become cases by the word rules alone`;
              })}>{status?.language_model === "on" ? "Switch off" : "Switch on"}</Button>
            </div>
          </Box>
          <Box title="A rush of reports">
            <div className="flex items-center justify-between gap-3">
              <span>{status?.surge
                ? <>Running: {status.surge.rate} a second, <span className="tabular">{status.surge.seconds_left}</span> s left. <a href="/surge" className="underline underline-offset-2">Watch it</a></>
                : <>50 made-up reports a second for 60 s, already sorted into fields, so no AI is called: say so.</>}</span>
              <Button size="sm" className="shrink-0 whitespace-nowrap" disabled={!!busy || !!status?.surge} onClick={() => run("Rush", async () => {
                await api("/v1/demo/surge", { method: "POST", json: { rate: 50, duration: 60 } });
                return "Started: open Show it under load on the projector";
              })}>Start</Button>
            </div>
          </Box>
          <Box title="The partner moment">
            <div className="flex items-center justify-between gap-3">
              <span>Our <b>simulated</b> partner system suggests a priority for BR-199, notes its clip, keeps a copy of our history, and has a replayed
                request refused. Say it&apos;s simulated.</span>
              <Button size="sm" className="shrink-0 whitespace-nowrap" disabled={!!busy} onClick={() => run("Partner moment", async () => {
                const r = await api<{ calls: string[] }>("/v1/demo/partner-moment", { method: "POST", json: { case: "BR-199" } });
                return r.calls.join(" · ");
              })}>Run it</Button>
            </div>
          </Box>
          <Box title="Play a recorded clip">
            <ul className="divide-y divide-line">
              {clips.map((c) => (
                <li key={c.clip} className="flex items-center justify-between gap-3 py-2">
                  <span>{c.clip} {c.synthetic && <span className="text-ink-3">· a synthetic voice, not a person</span>}</span>
                  <Button size="sm" disabled={!!busy} onClick={() => run("Play clip", async () => {
                    const r = await api<{ report_id: number }>("/v1/demo/play-clip", { method: "POST", json: { clip: c.clip } });
                    return `Played ${c.clip}: report ${r.report_id} is being read (watch the desk)`;
                  })}>Play</Button>
                </li>
              ))}
              {!clips.length && <li className="py-2 text-ink-3">No clips in data/scenarios/BR/clips/</li>}
            </ul>
          </Box>
        </div>
      </details>
    </Page>
    </AppShell>
  );
}

// The presenter's script: one line per scene, what to do and say (the ids are data/scenarios/BR/demo.yaml's).
const SCRIPT = [
  { id: "son", title: "A family asks for help", do: "Scan the QR with any phone and ask for help, by voice or text. It reaches the desk in seconds." },
  { id: "merge", title: "The same family, twice", do: "Paste a neighbour's message about the same family: merge it. A different family with the same surname stays apart." },
  { id: "sheet", title: "A volunteer's spreadsheet", do: "Add the 300-row sheet: new families appear, repeats merge, nothing is dropped." },
  { id: "stale", title: "A team goes quiet", do: "Send SDRF Boat 2 (radio only). It misses its check-in: contact overdue. Send another team." },
  { id: "rescue", title: "The rescue", do: "On Boat 5's phone: accept, reached, 4 taken, then 2. Rescued 6 of 6, and the family taps Yes." },
  { id: "receipts", title: "Proof", do: "Open the case's timeline: every item unchanged. History: nothing was changed." },
]

// The two pages that show the system under pressure and talking to another team's system (m69: out of the sidebar).
function Shows() {
  return (
    <div className="mt-6 grid gap-3 sm:grid-cols-2">
      <a href="/surge" className="rounded-2xl bg-paper px-5 py-4 shadow-[var(--shadow-card)] hover:bg-wash">
        <b>Show it under load</b><span className="block text-body text-ink-2">50 made-up reports a second: nothing lost, nothing doubled.</span></a>
      <a href="/partners" className="rounded-2xl bg-paper px-5 py-4 shadow-[var(--shadow-card)] hover:bg-wash">
        <b>Show a partner system</b><span className="block text-body text-ink-2">Another team&rsquo;s app sends signed notes (simulated by us).</span></a>
    </div>
  );
}

// Each control under its own heading.
function Box({ title, children }: { title: string; children: React.ReactNode }) {
  return <Section title={title}>{children}</Section>;
}

function Qr({ target, title, note }: { target: string; title: string; note: string }) {
  const [img, setImg] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {   // shown as an image, never as injected markup (R14)
    let made: string | null = null;
    fetch(`/v1/demo/qr?target=${target}`, { cache: "no-store" }).then(async (r) => {
      if (!r.ok) { setErr(((await r.json().catch(() => ({}))) as { detail?: string }).detail ?? `HTTP ${r.status}`); return; }
      setUrl(r.headers.get("X-QR-URL"));
      made = URL.createObjectURL(new Blob([await r.text()], { type: "image/svg+xml" }));
      setImg(made);
    }).catch((e) => setErr(String(e)));
    return () => { if (made) URL.revokeObjectURL(made); };
  }, [target]);
  return (
    <figure>
      <figcaption className="font-medium">{title}</figcaption>
      {img ? <img src={img} alt={`QR code: ${title}`} className="mt-2 w-44 rounded-xl border border-line bg-white p-2" /> : <p className="mt-2 text-ink-3">{err ?? "…"}</p>}
      {url && <p className="mt-1 break-all text-small text-ink-2">{url}</p>}
      <p className="mt-1 text-small text-ink-3">{note}</p>
    </figure>
  );
}
