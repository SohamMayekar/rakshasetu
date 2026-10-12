"use client";

// One case, one screen, no tabs (PRD F-C7): a map strip with the circle, THE CALLER'S OWN WORDS FIRST (in their
// script), Navigate (the phone's map app), Call (the number is revealed for the assigned team and the reveal is
// logged), "You own this · check-in due", and ONE state-driven button: Acknowledge → Reached → Record rescue.
// Everything else is under More. A case that isn't this team's shows the server's 403, plainly.

import { use, useCallback, useEffect, useState } from "react";

import { CaseMap } from "@/components/desk/CaseMap";
import { RescueSheet } from "@/components/rescue/RescueSheet";
import { BigButton, TapStatus } from "@/components/responder/Field";
import { Priority, Ring } from "@/components/ui";
import { api, ApiError, type CaseDetail } from "@/lib/api";
import { useWakeLock } from "@/lib/wakelock";
import { tap } from "@/lib/outbox";

export default function ResponderCase({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [c, setC] = useState<CaseDetail | null>(null);
  const [denied, setDenied] = useState<string | null>(null);
  const [more, setMore] = useState(false);
  const [releasing, setReleasing] = useState(false);
  const [rescuing, setRescuing] = useState(false);
  useEffect(() => { if (new URLSearchParams(location.search).get("rescue")) setRescuing(true); }, []);   // from My cases' "Record the rescue"
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<CaseDetail>(`/v1/cases/${id}`).then(setC).catch((e) => {
      if (e instanceof ApiError && e.status === 403) setDenied(String(e.detail));
      else if (e instanceof ApiError && e.status === 401) location.href = "/responder";
      else if (e instanceof ApiError && e.status === 404) setDenied("No such case");
    });
  }, [id]);
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);
  useWakeLock(["acknowledged", "reached"].includes(c?.assignment?.phase ?? ""));   // on the way or on scene: screen on

  if (denied) {
    return (
      <main className="mx-auto max-w-md px-5 py-10">
        <p className="text-small font-medium text-ink-2">Not your team&rsquo;s case</p>
        <h1 className="mt-1 text-2xl font-semibold">{denied}</h1>
        <p className="mt-2 text-ink-2">Your team can open only the cases assigned to it. Ask the control room on radio if you think this one should be yours.</p>
        {/* a rescue record that hands the case back (someone still there) ends the team's access: its taps still show */}
        <div className="mt-4"><TapStatus caseId={Number(id)} /></div>
        <a href="/responder" className="mt-6 block underline underline-offset-4">Back to my cases</a>
      </main>
    );
  }
  if (!c) return <main className="p-6 text-ink-3">…</main>;
  const a = c.assignment;
  const words = c.reports.find((r) => r.transcript || r.text);
  const call = async () => {
    setError(null);
    try {
      const r = await api<{ phone: string }>(`/v1/cases/${c.id}/reveal-contact`, { method: "POST", json: {} });
      location.href = `tel:${r.phone}`;
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const step = !a ? null : a.phase === "offered" ? "acknowledge" : a.phase === "acknowledged" ? "reached" : "rescue";

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col bg-canvas pb-6">
      <div className="m-3 mb-0 h-44 overflow-hidden rounded-card bg-wash shadow-[var(--shadow-card)]">{c.lat != null && <CaseMap cases={[c]} selected={c.id} onSelect={() => {}} />}</div>
      <div className="mx-3 mt-3 flex-1 rounded-card bg-paper px-5 py-4 shadow-[var(--shadow-card)]">
        <p className="flex items-baseline gap-3 text-3xl font-semibold tracking-tight"><Priority level={c.priority} /><span className="tabular">{c.public_id}</span></p>
        {words && (
          <p className="mt-3 whitespace-pre-line rounded-2xl rounded-tl-md bg-wash px-4 py-3 text-xl leading-snug" lang={words.language ?? undefined}>&ldquo;{words.transcript ?? words.text}&rdquo;</p>
        )}
        <p className="mt-2 text-lg text-ink-2">{c.summary}</p>
        <p className="mt-1 text-ink-2">{c.location_text ?? "Place not known"}{c.radius_m ? ` · within about ${c.radius_m >= 1000 ? `${c.radius_m / 1000} km` : `${c.radius_m} m`}` : ""}</p>
        {c.location_confidence && c.location_confidence !== "high" && <p className="text-body text-ink-3">The place is approximate: search the circle.</p>}
        {c.lat != null && <a href={`geo:${c.lat},${c.lng}?q=${c.lat},${c.lng}(${c.public_id})`} className="mt-4 flex min-h-14 items-center justify-center rounded-2xl border-2 border-ink font-semibold">Navigate</a>}
        {a && (
          <div className="mt-4 rounded-2xl bg-wash px-4 py-3">
            <p className="font-medium">Your team has this</p>
            <Ring due={a.next_contact_due} windowMs={Math.max(new Date(a.next_contact_due).getTime() - new Date(a.created_at).getTime(), 60_000)}
                  overdue={a.state === "overdue"} demo={a.demo_clock} />
          </div>
        )}
        {error && <p className="mt-2 text-body">{error}</p>}
      </div>
      <div className="space-y-3 px-5 pt-4">
        <TapStatus caseId={c.id} />
        {step === "acknowledge" && <p className="text-center text-body text-ink-2">Accept: we&rsquo;ll be there in</p>}
        {step === "acknowledge" && (
          <div className="grid grid-cols-3 gap-3">
            {[15, 30, 60].map((m) => (
              <BigButton key={m} variant={m === 30 ? "primary" : "secondary"}
                         onClick={() => tap({ url: `/v1/assignments/${a!.id}/acknowledge`, body: { eta_minutes: m }, label: `Accepted · ETA ${m} min`, caseId: c.id })}>
                {m} min
              </BigButton>
            ))}
          </div>
        )}
        {step === "reached" && (
          <BigButton onClick={() => tap({ url: `/v1/assignments/${a!.id}/reached`, label: "Reached", caseId: c.id })}>I&rsquo;ve reached them</BigButton>
        )}
        {step === "rescue" && !rescuing && <BigButton onClick={() => setRescuing(true)}>Record the rescue</BigButton>}
        {rescuing && (
          <RescueSheet reported={c.people_remaining ?? c.people_count} onRecord={(body, label) => {   // a second trip starts at who's left
            // the team phone's own location at that moment (not the family's), if the phone will give it quickly.
            // The record never waits on it: an unanswered location prompt calls neither callback (the timeout only
            // starts once permission is given), so a hard 3.5 s fallback saves it without a position, once.
            let saved = false;
            const send = (pos?: GeolocationPosition) => {
              if (saved) return;
              saved = true;
              tap({ url: `/v1/cases/${c.id}/rescues`, label, caseId: c.id,
                    body: { ...body, ...(pos ? { lat: pos.coords.latitude, lng: pos.coords.longitude } : {}) } });
            };
            if (navigator.geolocation) {
              navigator.geolocation.getCurrentPosition((p) => send(p), () => send(), { timeout: 3000, maximumAge: 60_000 });
              setTimeout(() => send(), 3500);
            } else send();
            setRescuing(false);
          }} />
        )}
        <button onClick={() => setMore(!more)} className="min-h-12 w-full text-base underline underline-offset-4">More</button>
        {more && a && (
          <div className="space-y-2">
            <BigButton variant="secondary" onClick={call}>Call the family (the number is shown to you; it&rsquo;s logged)</BigButton>
            {!releasing ? <BigButton variant="secondary" onClick={() => setReleasing(true)}>Hand this case back</BigButton> : (
              <form className="space-y-2" onSubmit={(e) => { e.preventDefault();
                tap({ url: `/v1/assignments/${a.id}/release`, body: { reason: String(new FormData(e.currentTarget).get("reason")) }, label: "Handed back", caseId: c.id });
                setReleasing(false); }}>
                <input name="reason" required minLength={3} placeholder="Why? e.g. boat engine failed" className="h-14 w-full rounded-xl border border-line px-4 text-lg" />
                <BigButton>Hand back</BigButton>
              </form>
            )}
          </div>
        )}
        <a href="/responder" className="block py-2 text-center underline underline-offset-4">My cases</a>
      </div>
    </main>
  );
}
