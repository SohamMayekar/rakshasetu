// Signing out, for every kind of account (desk staff, a rescue team, the national admin). One place, so every
// screen that offers it behaves the same: the cookie is cleared first, then the person lands on the home page.
// Visiting the home page, the help page or the status page never needs a session, and never signs anyone out.

export async function signOut(to = "/"): Promise<void> {
  try {
    await fetch("/v1/auth/logout", { method: "POST", keepalive: true });
  } catch { /* offline or the server is down: still leave the signed-in screens */ }
  try { sessionStorage.clear(); } catch { /* blocked storage */ }
  location.href = to;
}
