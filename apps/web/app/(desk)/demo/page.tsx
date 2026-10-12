"use client";

// Demo controls (PRD F-C12): local listener only, DEMO_MODE only, Demo admin. Reset to a scene's starting
// point, the language model off/on, a surge, a recorded clip through the live pipeline, and QR codes for phones.
// Open it at http://127.0.0.1/demo signed in as Demo admin, and keep the desk on http://localhost: the two
// addresses keep separate sign-ins, so the officer on the projector stays signed in.

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
        <PageHeader title="Demo" sub="The 5-minute story, scene by scene. Every person and phone number is made up; the demo clock runs 60× faster." />
        <Shows />
        <Card className="mt-4 px-5 py-4 text-sm">
          <ol className="space-y-2">{SCRIPT.map((x, i) => <li key={x.id}><b className="tabular">{i + 1}. {x.title}</b> <span className="text-ink-2">· {x.do}</span></li>)}</ol>
          <p className="mt-3 text-ink-3">The reset buttons and QR codes are for the Demo admin: open <b>http://127.0.0.1/demo</b> and sign in as Demo admin
            there, so this desk on <b>http://localhost</b> stays signed in as {me.user.name}.</p>
        </Card>
      </Page></AppShell>
    );
  }

  return (
    <AppShell me={me}>
    <Page>
      <PageHeader title="Demo controls" sub="Local only, demo mode only. Every control here is on the audit log." />
      {line && <p className="mt-4 rounded-xl bg-paper px-4 py-2.5 text-sm shadow-[var(--shadow-card)]" role="status">{line}</p>}
      <Shows />
      <div className="text-sm">

      <Box title="Reset to a scene">
        <p className="mb-2 text-ink-2">Wipes the database, seeds it with times relative to now, then plays every scene before the one you pick
          through the real API. Every open screen reloads itself.</p>
        <ol className="divide-y divide-line">
          {scenes.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 py-2">
              <span className="min-w-0"><span className="tabular text-ink-3">{s.at}</span> <b>{s.title}</b>
                <span className="block text-ink-2">{s.starts_with}</span></span>
              <Button size="sm" className="shrink-0 whitespace-nowrap" disabled={!!busy} onClick={() => run(`Reset to ${s.title}`, async () => {
                const r = await api<Reset>("/v1/demo/reset", { method: "POST", json: { scene: s.id } });
                return `Reset to “${s.title}” in ${r.seconds} s${r.son_case ? ` · the son's case is ${r.son_case}` : ""}`;
              })}>{busy === `Reset to ${s.title}` ? "Resetting…" : "Reset here"}</Button>
            </li>
          ))}
        </ol>
      </Box>

      <Box title="Language model">
        <div className="flex items-center justify-between gap-3">
          <span>
            {status && !status.keys.llm.length
              ? <>The switch is <b>{status.language_model}</b>, but no language-model key is set (<code>GROQ_API_KEY</code>, <code>GEMINI_API_KEY</code>):
                  the keyword rules read every report either way.</>
              : <>The language model is <b>{status?.language_model ?? "…"}</b>{status ? ` (${status.keys.llm.join(", ")})` : ""}.
                  Speech-to-text stays on: say “language model”, not “AI”.</>}
            <span className="block text-ink-3">Speech-to-text: {status?.keys.stt.length ? status.keys.stt.join(", ")
              : "no key: a clip without a recorded transcript becomes an “audio only” case"}.</span>
          </span>
          <Button size="sm" className="shrink-0 whitespace-nowrap" disabled={!!busy || !status} onClick={() => run("Language model", async () => {
            const on = status?.language_model !== "on";
            await api("/v1/demo/language-model", { method: "POST", json: { on } });
            return `Language model ${on ? "on" : "off"}: typed reports become cases by the keyword rules alone`;
          })}>{status?.language_model === "on" ? "Switch off" : "Switch on"}</Button>
        </div>
      </Box>

      <Box title="Surge">
        <div className="flex items-center justify-between gap-3">
          <span>{status?.surge
            ? <>Running: {status.surge.rate} reports a second, <span className="tabular">{status.surge.seconds_left}</span> s left. <a href="/surge" className="underline underline-offset-2">Watch it</a></>
            : <>50 synthetic, pre-structured partner reports a second for 60 s. No language model is called: say so. <a href="/surge" className="underline underline-offset-2">Surge screen</a></>}</span>
          <Button size="sm" className="shrink-0 whitespace-nowrap" disabled={!!busy || !!status?.surge} onClick={() => run("Surge", async () => {
            await api("/v1/demo/surge", { method: "POST", json: { rate: 50, duration: 60 } });
            return "Surge started: open /surge on the projector";
          })}>Start surge</Button>
        </div>
      </Box>

      <Box title="Partner moment">
        <div className="flex items-center justify-between gap-3">
          <span>A <b>simulated</b> partner (our own script, signed, through the public address) suggests a priority for BR-199, notes its
            clip, anchors our audit head, and has a replayed request refused. Say it&apos;s simulated. <a href="/partners" className="underline underline-offset-2">Partner log</a></span>
          <Button size="sm" className="shrink-0 whitespace-nowrap" disabled={!!busy} onClick={() => run("Partner moment", async () => {
            const r = await api<{ calls: string[] }>("/v1/demo/partner-moment", { method: "POST", json: { case: "BR-199" } });
            return r.calls.join(" · ");
          })}>Run it</Button>
        </div>
      </Box>

      <Box title="Play a recorded clip">
        <p className="mb-2 text-ink-2">The fallback if live voice fails: the clip goes in the same way as from the reporter page,
          from the son&apos;s phone. Say it&apos;s a recording.</p>
        <ul className="divide-y divide-line border-y border-line">
          {clips.map((c) => (
            <li key={c.clip} className="flex items-center justify-between gap-3 py-2">
              <span>{c.clip} {c.synthetic && <span className="text-ink-3">· synthetic voice, not a person</span>}</span>
              <Button size="sm" disabled={!!busy} onClick={() => run("Play clip", async () => {
                const r = await api<{ report_id: number }>("/v1/demo/play-clip", { method: "POST", json: { clip: c.clip } });
                return `Played ${c.clip}: report ${r.report_id} is being read (watch the desk)`;
              })}>Play</Button>
            </li>
          ))}
          {!clips.length && <li className="py-2 text-ink-3">No clips in data/scenarios/BR/clips/</li>}
        </ul>
      </Box>

      <Box title="Phones">
        {status && !status.public_url
          ? <p className="text-ink-2">Set <code>PUBLIC_URL</code> in <code>.env</code> to the tunnel&apos;s address for the phone QR codes.</p>
          : (
            <div className="grid gap-6 sm:grid-cols-2">
              <Qr key={`r${qrKey}`} target="reporter" title="Reporter page" note="The judge's phone, or a spare." />
              <Qr key={`s${qrKey}`} target="son" title="The son's status page, as his phone"
                  note="After a reset past the rescue: the family's question is asked only of the phone that reported." />
            </div>
          )}
      </Box>
      </div>
    </Page>
    </AppShell>
  );
}

// The presenter's script: one line per scene, what to do and say (the ids are data/scenarios/BR/demo.yaml's).
const SCRIPT = [
  { id: "son", title: "The son", do: "A son in Mumbai speaks one sentence into the phone app; it becomes a case on the desk." },
  { id: "merge", title: "Never doubled", do: "A neighbour's forward is the same family: merge it. Rajesh ≠ Ramesh: kept apart." },
  { id: "sheet", title: "The volunteer sheet", do: "Add a 300-row sheet: new families, repeats merged, nothing dropped." },
  { id: "stale", title: "Never stale", do: "Send SDRF Boat 2; it goes quiet; contact overdue; send another team." },
  { id: "rescue", title: "The rescue", do: "Boat 5's phone: accept, reached, 4 taken, then 2: rescued 6 of 6; the son says yes." },
  { id: "receipts", title: "The receipts", do: "Timeline & evidence, each item ✓; History: nothing was changed." },
];

// The two pages that show the system under pressure and talking to another team's system (m69: out of the sidebar).
function Shows() {
  return (
    <div className="mt-5 grid gap-3 sm:grid-cols-2">
      <a href="/surge" className="rounded-2xl bg-paper px-5 py-4 shadow-[var(--shadow-card)] hover:bg-wash">
        <b>Show it under load</b><span className="block text-sm text-ink-2">50 made-up reports a second: nothing lost, nothing doubled.</span></a>
      <a href="/partners" className="rounded-2xl bg-paper px-5 py-4 shadow-[var(--shadow-card)] hover:bg-wash">
        <b>Show a partner system</b><span className="block text-sm text-ink-2">Another team&rsquo;s app sends signed notes (simulated by us).</span></a>
    </div>
  );
}

// Each control in its own card.
function Box({ title, children }: { title: string; children: React.ReactNode }) {
  return <Card className="mt-4 px-5"><Section title={title}>{children}</Section></Card>;
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
      {url && <p className="mt-1 break-all text-xs text-ink-2">{url}</p>}
      <p className="mt-1 text-xs text-ink-3">{note}</p>
    </figure>
  );
}
