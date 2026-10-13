// Native stand-in for Caddy's local listener (PRD §12, rule R18).
// Listens on :3000 and forwards:
//   /v1/* (incl. the /v1/ws WebSocket) + /healthz → api :8000, with X-RS-Listener: local
//   everything else (pages, assets)                  → web :3100 (next start)
// That header is what Caddy set on its local listener; the API hides desk endpoints without it.
import http from "node:http";

const API = { host: "127.0.0.1", port: 8000 };
const WEB = { host: "127.0.0.1", port: 3100 };

const isApi = (url) => url === "/healthz" || url === "/v1" || url.startsWith("/v1/");

const server = http.createServer((req, res) => {
  const up = isApi(req.url) ? API : WEB;
  const headers = isApi(req.url) ? { ...req.headers, "x-rs-listener": "local" } : req.headers;
  const proxyReq = http.request({ ...up, path: req.url, method: req.method, headers }, (upRes) => {
    res.writeHead(upRes.statusCode, upRes.headers);
    upRes.pipe(res);
  });
  proxyReq.on("error", (e) => {
    res.writeHead(502, { "content-type": "text/plain" });
    res.end(`${up.port === API.port ? "api" : "web"} unreachable: ${e.message}`);
  });
  req.pipe(proxyReq);
});

server.on("upgrade", (req, socket, head) => {
  // Only the API speaks WebSocket (/v1/ws live stream).
  const headers = { ...req.headers, "x-rs-listener": "local" };
  const proxyReq = http.request({ ...API, path: req.url, method: req.method, headers });
  proxyReq.on("upgrade", (upRes, upSocket, upHead) => {
    const lines = [`HTTP/1.1 101 Switching Protocols`];
    for (const [k, v] of Object.entries(upRes.headers)) lines.push(`${k}: ${Array.isArray(v) ? v.join(", ") : v}`);
    socket.write(lines.join("\r\n") + "\r\n\r\n");
    if (upHead?.length) upSocket.write(upHead);
    upSocket.pipe(socket);
    socket.pipe(upSocket);
    const drop = () => { upSocket.destroy(); socket.destroy(); };
    upSocket.on("error", drop);
    socket.on("error", drop);
  });
  proxyReq.on("error", () => socket.destroy());
  proxyReq.end();
});

server.listen(3000, () => console.log("rakshasetu proxy :3000 → api :8000 (local listener) + web :3100"));
