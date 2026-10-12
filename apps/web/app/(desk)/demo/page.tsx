"use client";

// Demo controls (PRD F-C12): local listener only, DEMO_MODE only, System admin. Reset to a scene's starting
// point, the language model off/on, a surge, a recorded clip through the live pipeline, and QR codes for phones.
// Open it at http://127.0.0.1/demo signed in as System admin, and keep the desk on http://localhost: the two
// addresses keep separate sign-ins, so the officer on the projector stays signed in.

import { useCallback, useEffect, useState } from "react";

import { Button, Section } from "@/components/ui";
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

  if (me && me.user.role !== "admin") {
    return (
      <main className="mx-auto max-w-2xl px-4 py-8 text-sm">
        <h1 className="text-2xl font-semibold tracking-tight">Demo controls</h1>
        <p className="mt-2 text-ink-2">These need the System admin. Open <b>http://127.0.0.1/demo</b> and sign in as System admin there,
          so the desk on <b>http://localhost</b> stays signed in as {me.user.name}.</p>
        <p className="mt-3"><a href="/login" className="underline underline-offset-2">Sign in as someone else</a></p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 text-sm">
      <p><a href="/" className="underline underline-offset-2">Incidents</a></p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Demo controls</h1>
      <p className="mt-1 text-ink-2">Local only, demo mode only. Every control here is on the audit log.</p>
      {line && <p className="mt-3 rounded bg-wash px-3 py-2" role="status">{line}</p>}

      <Section title="Reset to a scene">
        <p className="mb-2 text-ink-2">Wipes the database, seeds it with times relative to now, then plays every scene before the one you pick
          through the real API. Every open screen reloads itself.</p>
        <ol className="divide-y divide-line border-y border-line">
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
      </Section>

      <Section title="Language model">
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
      </Section>

      <Section title="Surge">
        <div className="flex items-center justify-between gap-3">
          <span>{status?.surge
            ? <>Running: {status.surge.rate} reports a second, <span className="tabular">{status.surge.seconds_left}</span> s left. <a href="/surge" className="underline underline-offset-2">Watch it</a></>
            : <>50 synthetic, pre-structured partner reports a second for 60 s. No language model is called: say so. <a href="/surge" className="underline underline-offset-2">Surge screen</a></>}</span>
          <Button size="sm" className="shrink-0 whitespace-nowrap" disabled={!!busy || !!status?.surge} onClick={() => run("Surge", async () => {
            await api("/v1/demo/surge", { method: "POST", json: { rate: 50, duration: 60 } });
            return "Surge started: open /surge on the projector";
          })}>Start surge</Button>
        </div>
      </Section>

      <Section title="Play a recorded clip">
        <p className="mb-2 text-ink-2">The fallback if live voice fails: the clip goes through the same pipeline as the reporter page,
          from the son&apos;s phone. Say it&apos;s a recording.</p>
        <ul className="divide-y divide-line border-y border-line">
          {clips.map((c) => (
            <li key={c.clip} className="flex items-center justify-between gap-3 py-2">
              <span>{c.clip} {c.synthetic && <span className="text-ink-3">· synthetic voice, not a person</span>}</span>
              <Button size="sm" disabled={!!busy} onClick={() => run("Play clip", async () => {
                const r = await api<{ report_id: number }>("/v1/demo/play-clip", { method: "POST", json: { clip: c.clip } });
                return `Played ${c.clip}: report ${r.report_id} is in the pipeline (watch the desk)`;
              })}>Play</Button>
            </li>
          ))}
          {!clips.length && <li className="py-2 text-ink-3">No clips in data/scenarios/BR/clips/</li>}
        </ul>
      </Section>

      <Section title="Phones">
        {status && !status.public_url
          ? <p className="text-ink-2">Set <code>PUBLIC_URL</code> in <code>.env</code> to the tunnel&apos;s address for the phone QR codes.</p>
          : (
            <div className="grid gap-6 sm:grid-cols-2">
              <Qr key={`r${qrKey}`} target="reporter" title="Reporter page" note="The judge's phone, or a spare." />
              <Qr key={`s${qrKey}`} target="son" title="The son's status page, as his phone"
                  note="After a reset past the rescue: the family's question is asked only of the phone that reported." />
            </div>
          )}
      </Section>
    </main>
  );
}

function Qr({ target, title, note }: { target: string; title: string; note: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    fetch(`/v1/demo/qr?target=${target}`, { cache: "no-store" }).then(async (r) => {
      if (!r.ok) { setErr(((await r.json().catch(() => ({}))) as { detail?: string }).detail ?? `HTTP ${r.status}`); return; }
      setUrl(r.headers.get("X-QR-URL")); setSvg(await r.text());
    }).catch((e) => setErr(String(e)));
  }, [target]);
  return (
    <figure>
      <figcaption className="font-medium">{title}</figcaption>
      {svg ? <div className="mt-2 w-fit bg-white p-1" dangerouslySetInnerHTML={{ __html: svg }} /> : <p className="mt-2 text-ink-3">{err ?? "…"}</p>}
      {url && <p className="mt-1 break-all text-xs text-ink-2">{url}</p>}
      <p className="mt-1 text-xs text-ink-3">{note}</p>
    </figure>
  );
}
