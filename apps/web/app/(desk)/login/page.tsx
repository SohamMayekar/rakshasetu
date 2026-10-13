"use client";

// Sign in with a username and a password. The demo's one-tap choices live on the door (/) — this page is the
// plain way in for anyone else (and the way back after a sign-out).

import { useEffect, useState } from "react";

import { Mark } from "@/components/shell/Sidebar";
import { Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { signOut } from "@/lib/session";

// Everyone on the desk side lands on the one national desk; a rescue team lands on its phone app.
const HOME: Record<string, string> = {
  call_taker: "/desk", duty_officer: "/desk", incharge: "/desk", admin: "/desk", seoc_viewer: "/?incidents", team_lead: "/responder",
};

async function enter(username: string, password: string) {
  await api("/v1/auth/login", { method: "POST", json: { username, password } });
  const me = await api<{ user: { role: string } }>("/v1/me");
  location.href = HOME[me.user.role] ?? "/";
}

export default function Login() {
  const [error, setError] = useState<string | null>(null);
  // Already signed in (as anyone)? Say so, and offer to carry on or to sign out, instead of a form that would
  // quietly replace who they are.
  const [who, setWho] = useState<{ name: string; role: string; label: string } | null | undefined>(undefined);
  useEffect(() => {
    api<{ user: { name: string; role: string; role_label: string } }>("/v1/me")
      .then((m) => setWho({ name: m.user.name, role: m.user.role, label: m.user.role_label }))
      .catch(() => setWho(null));
  }, []);

  return (
    <main className="grid min-h-dvh place-items-center bg-canvas px-4 py-10">
      <Card className="w-full max-w-xl p-6 md:p-8">
        <div className="flex items-center gap-2.5"><Mark className="size-8 text-ink" /><span className="text-heading font-semibold tracking-tight">RakshaSetu</span></div>
        {who ? (
          <>
            <h1 className="mt-6 text-display font-semibold tracking-tight">You are signed in</h1>
            <p className="mt-2 text-body text-ink-2"><b className="font-semibold text-ink">{who.name}</b> · {who.label}</p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <Button variant="primary" onClick={() => { location.href = HOME[who.role] ?? "/"; }}>Continue</Button>
              <Button onClick={() => void signOut("/")}>Sign out</Button>
              <Button variant="quiet" onClick={() => { location.href = "/"; }}>Home page</Button>
            </div>
          </>
        ) : who === undefined ? (
          <p className="mt-6 text-body text-ink-3">…</p>
        ) : (<>
        <h1 className="mt-6 text-display font-semibold tracking-tight">Sign in</h1>
        <form className="mt-6 space-y-3" onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          enter(String(f.get("username")), String(f.get("password"))).catch((err) => setError(String(err.message)));
        }}>
          <input name="username" placeholder="Username" autoComplete="username" className="field" />
          <input name="password" type="password" placeholder="Password" autoComplete="current-password" className="field" />
          <Button variant="primary" type="submit">Sign in</Button>
        </form>
        {error && <p className="mt-4 text-body text-ink">{error}</p>}
        <p className="mt-6 text-small text-ink-2">Not sure who you are? The door at <a className="underline underline-offset-4" href="/?door=1">the front</a> has the three ways in, or go back to the <a className="underline underline-offset-4" href="/">home page</a>.</p>
        </>)}
      </Card>
    </main>
  );
}
