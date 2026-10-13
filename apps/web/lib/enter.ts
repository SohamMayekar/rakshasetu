// One tap into the national desk. On the demo listener the picker lists the admin profile, which signs in with no
// password and sees every incident; anywhere else (or if that fails) the plain sign-in page asks for one.

import { api } from "@/lib/api";

type Profile = { username: string; role: string };

export async function enterNationalDesk(): Promise<void> {
  try {
    // Already signed in as desk staff: just go to the desk, never swap who they are.
    const me = await api<{ user: { role: string } }>("/v1/me").catch(() => null);
    if (me && ["admin", "duty_officer", "incharge", "call_taker"].includes(me.user.role)) { location.href = "/desk"; return; }
    const profiles = await api<Profile[]>("/v1/auth/users");
    const who = profiles.find((p) => p.role === "admin") ?? profiles.find((p) => ["duty_officer", "incharge", "call_taker"].includes(p.role));
    if (!who) throw new Error("no desk profile");
    await api("/v1/auth/login", { method: "POST", json: { username: who.username } });
    location.href = "/desk";
  } catch {
    location.href = "/login";
  }
}
