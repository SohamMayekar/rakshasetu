// The team app's offline shell (PRD P1 #7). Network FIRST, always: online, the phone gets the live app (never a
// stale build); with no network, the last copy of the app it loaded. The API is never cached here: the page
// keeps its own last list of My cases and says how old it is. Taps wait in the phone's outbox.
const CACHE = "rs-responder-v1";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/v1/")) return;
  const keep = req.mode === "navigate" || url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/");
  if (!keep) return;
  e.respondWith(fetch(req).then((res) => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
    return res;
  }).catch(() => caches.match(req).then((hit) => hit || caches.match("/responder"))));
});
