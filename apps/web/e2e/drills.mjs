// Failure drills on the running stack (PRD §16.4 "fallbacks", §13.6 T2, F-C10 "done when"): each one breaks
// something on purpose, then measures how the system and the screens recover. Prints one line per check;
// exit 1 if any fails. Results go in docs/DRILLS.md by hand, from this output only.
//
//   make drills          (needs make up and docker; resets the demo first and after)

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { chromium, request } from "@playwright/test";

const DESK = "http://localhost", LOCAL = "http://127.0.0.1", PUBLIC = "http://127.0.0.1:8080";
const COMPOSE = ["compose", "-f", "../../infra/docker-compose.yml", "--env-file", "../../.env"];
const t0 = Date.now();
let failed = 0;
const say = (s) => console.log(`${((Date.now() - t0) / 1000).toFixed(1).padStart(6)} s  ${s}`);
const check = (ok, what) => { say(`${ok ? "✓" : "✗"} ${what}`); if (!ok) failed++; return ok; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const until = async (fn, ms = 30000, every = 250) => {
  const end = Date.now() + ms;
  for (;;) { const v = await fn().catch(() => null); if (v) return v; if (Date.now() > end) return null; await sleep(every); }
};
const docker = (...args) => execFileSync("docker", args, { encoding: "utf8" }).trim();
const sql = (q) => docker(...COMPOSE, "exec", "-T", "db", "psql", "-U", "postgres", "-d", "rakshasetu", "-tAc", q);

const admin = await request.newContext({ baseURL: LOCAL });
await admin.post("/v1/auth/login", { data: { username: "admin" } });
const officer = await request.newContext({ baseURL: LOCAL });
await officer.post("/v1/auth/login", { data: { username: "rdas" } });
const json = async (r) => (await r).json();
const integrity = async () => json(officer.get("/v1/integrity"));
const reset = async (scene = "son") => json(admin.post("/v1/demo/reset", { data: { scene } }));

const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY, bypass: "127.0.0.1,localhost" } : undefined;
const browser = await chromium.launch({ proxy, executablePath: process.env.CHROMIUM ?? (existsSync("/opt/pw-browsers/chromium") ? "/opt/pw-browsers/chromium" : undefined) });
async function desk() {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  await page.request.post(`${DESK}/v1/auth/login`, { data: { username: "rdas" } });
  await page.goto(`${DESK}/desk/BR`);
  await page.locator("ol[aria-label='Needs you now'] li").first().waitFor();
  return { ctx, page, header: () => page.locator("header").first().innerText({ timeout: 300 }) };
}

try {
  // ---- D1: the worker crashes mid-surge (T2, live) ------------------------------------------------------------
  say("D1 · the worker crashes in the middle of a surge");
  await reset();
  await admin.post("/v1/demo/surge", { data: { rate: 30, duration: 20 } });
  await sleep(8000);
  const pid = docker("inspect", "-f", "{{.State.Pid}}", "rakshasetu-worker-1");
  const restartsBefore = Number(docker("inspect", "-f", "{{.RestartCount}}", "rakshasetu-worker-1"));
  execFileSync("kill", ["-9", pid]);                      // a real crash: the process dies, not a docker stop
  const killedAt = Date.now();
  say(`  killed the worker process (pid ${pid}) 8 s into a 30/s surge`);
  const back = await until(async () => Number(docker("inspect", "-f", "{{.RestartCount}}", "rakshasetu-worker-1")) > restartsBefore
    && docker("inspect", "-f", "{{.State.Running}}", "rakshasetu-worker-1") === "true", 60000, 500);
  check(!!back, `the worker came back by itself in ${((Date.now() - killedAt) / 1000).toFixed(1)} s (restart: unless-stopped)`);
  const drained = await until(async () => {
    const m = await json(officer.get("/v1/metrics/surge"));
    return !m.lanes.surge && Number(sql("SELECT count(*) FROM jobs WHERE done_at IS NULL AND dead_at IS NULL")) === 0;
  }, 180000, 1000);
  check(!!drained, `the backlog drained ${((Date.now() - killedAt) / 1000).toFixed(0)} s after the crash (jobs the dead worker held are reclaimed after 60 s)`);
  const surge = Number(sql("SELECT count(*) FROM reports WHERE source->>'system' = 'surge.py'"));
  const homeless = Number(sql("SELECT count(*) FROM reports WHERE source->>'system' = 'surge.py' AND case_id IS NULL"));
  const twice = Number(sql("SELECT count(*) FROM (SELECT body::jsonb->'data'->>'report_id' FROM events WHERE action = 'case.created' GROUP BY 1 HAVING count(*) > 1) x"));
  check(homeless === 0 && twice === 0, `all ${surge} surge reports are in exactly one case (${homeless} without, ${twice} made twice)`);
  const i1 = await integrity();
  check(i1.problems === 0, `integrity: ${i1.problems} problems, ${i1.events_verified} events verified`);

  // ---- D2: the desk's link to the server drops for 30 s (F-C10 "done when") -------------------------------------
  // (Chromium's offline emulation leaves an open WebSocket connected, so the drill cuts the real path instead:
  // the proxy between the projector and the API stops for 30 s, while a report arrives inside the server.)
  say("D2 · the desk's link to the server drops for 30 s while a report arrives");
  await reset();
  const d = await desk();
  const cutAt = Date.now();
  docker("stop", "-t", "0", "rakshasetu-caddy-1");
  const paused = await until(async () => /Live updates paused since/.test(await d.header()), 15000);
  check(!!paused, `the header says "Live updates paused since …" (not a silent stale screen)`);
  const rid = docker(...COMPOSE, "exec", "-T", "api", "python", "-c", `
from app.contracts import CanonicalReport
from app.core.eventlog import Actor
from app.db import get_engine
from app.modules.intake.service import accept
r = CanonicalReport.model_validate({"schema_version": "1", "idempotency_key": "drill-d2", "channel": "partner", "incident_hint": "BR",
    "content": {"text": "Kuchaikote gaon mein, station ke paas, 5 log chhat par fase hain, bachche hain"}, "source": {"system": "drill"}})
with get_engine().begin() as c:
    print(accept(c, r, source_ns="partner:drill", actor=Actor("partner", "drill", "partner")).report_id)`);
  const madePid = await until(async () => sql(`SELECT c.public_id FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.id = ${rid}`), 20000);
  say(`  while the desk was cut off: report ${rid} became ${madePid}`);
  await sleep(Math.max(0, 30000 - (Date.now() - cutAt)));
  docker("start", "rakshasetu-caddy-1");
  const online = Date.now();
  const live = await until(async () => /\bLive\b/.test(await d.header()) && !/paused/.test(await d.header()), 60000);
  const pill = d.page.getByRole("button", { name: /new: show/ });
  const caught = await until(async () => { if (await pill.isVisible()) await pill.click(); return (await d.page.locator("ol[aria-label='Needs you now']").innerText({ timeout: 300 })).includes(madePid); }, 30000);
  check(!!live && !!caught, `after 30 s cut off: live again and ${madePid} on the desk ${((Date.now() - online) / 1000).toFixed(1)} s after the link came back, no reload`);
  await d.page.screenshot({ path: "../../docs/screens/m56/drill-desk-back-online-desk.png" });

  // ---- D3: the API process restarts ---------------------------------------------------------------------------
  say("D3 · the API restarts under an open desk");
  const restartAt = Date.now();
  docker("restart", "rakshasetu-api-1");
  const pausedApi = await until(async () => /paused/.test(await d.header()), 20000);
  const healthy = await until(async () => (await (await fetch(`${LOCAL}/healthz`)).ok), 60000, 500);
  const relive = await until(async () => /\bLive\b/.test(await d.header()) && !/paused/.test(await d.header()), 60000);
  check(!!healthy && !!relive, `API back in ${((Date.now() - restartAt) / 1000).toFixed(1)} s; the desk said "paused" (${pausedApi ? "yes" : "no"}) and reconnected by itself`);
  await officer.post("/v1/auth/login", { data: { username: "rdas" } });   // sessions survive (stateless cookie)? re-sign the script only
  const rid2 = (await json(officer.post("/v1/ingest/desk", { data: { incident: "BR", text: "Mirganj mein 3 log ghar ke andar fase hain",
    phone: "+91 98765 73002", client_id: `drill2-${Date.now()}` } }))).report_id;
  const after = await until(async () => { if (await pill.isVisible()) await pill.click(); return (await d.page.locator("ol[aria-label='Needs you now']").innerText({ timeout: 300 })).match(/BR-\d+(?=[\s\S]*3 people)/)?.[0]; }, 20000);
  check(!!after, `a report after the restart (report ${rid2}) reaches the open desk without a reload`);
  await d.ctx.close();

  // ---- D4: the map tile server is unreachable (venue network) -------------------------------------------------
  say("D4 · the map's tile server is unreachable");
  const ctx4 = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await ctx4.route(/openfreemap|tiles\./, (r) => r.abort());
  const p4 = await ctx4.newPage();
  await p4.request.post(`${DESK}/v1/auth/login`, { data: { username: "rdas" } });
  await p4.goto(`${DESK}/desk/BR`);
  const paper = await until(async () => (await p4.locator("main").innerText({ timeout: 300 })).includes("Map tiles unavailable"), 15000);
  check(!!paper, `plain paper with the circles, and it says so: "Map tiles unavailable: circles only"`);
  await p4.screenshot({ path: "../../docs/screens/m56/drill-tiles-down-desk.png" });
  await ctx4.close();

  // ---- D5: the language model is off (F-C14) ------------------------------------------------------------------
  say("D5 · the language model is switched off");
  await admin.post("/v1/demo/language-model", { data: { on: false } });
  const s5 = Date.now();
  const rid5 = (await json(officer.post("/v1/ingest/desk", { data: { incident: "BR", text: "Barauli mein 4 log chhat par, ek buzurg hain, dawai chahiye",
    phone: "+91 98765 73005", client_id: `drill5-${Date.now()}` } }))).report_id;
  const made5 = await until(async () => sql(`SELECT c.public_id || ' ' || r.extraction_method FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.id = ${rid5}`), 10000);
  check(!!made5 && (Date.now() - s5) <= 5000 && made5.endsWith("rules"), `a typed report became ${made5?.split(" ")[0]} in ${((Date.now() - s5) / 1000).toFixed(1)} s, read by the rules (≤ 5 s)`);
  await admin.post("/v1/demo/language-model", { data: { on: true } });

  // ---- D6: an insider edits history (the tamper demo, Q&A) -----------------------------------------------------
  say("D6 · a database superuser quietly edits one past event");
  execFileSync("bash", ["-c", "cd ../.. && make -s tamper SEQ=12 >/dev/null"]);
  const v = await json(officer.get("/v1/audit/verify"));
  check(v.ok === false && v.broken_at === 12, `Verify chain: broken at #${v.broken_at} (${v.problem})`);
  const r6 = await reset();
  const v2 = await json(officer.get("/v1/audit/verify"));
  check(v2.ok === true, `a reset (${r6.seconds} s) starts a fresh chain: ✓ ${v2.count} events verified`);

  // ---- D7: a scene fails on stage → reset to that scene ---------------------------------------------------------
  say("D7 · a scene fails: reset to its starting point");
  const r7 = await reset("rescue");
  const owner = sql("SELECT t.name || ' / ' || a.phase || ' / demo_clock=' || a.demo_clock FROM assignments a JOIN teams t ON t.id = a.team_id JOIN cases c ON c.id = a.case_id WHERE c.public_id = 'BR-199' AND a.state = 'open'");
  check(r7.scene === "rescue" && owner.startsWith("Fire & Rescue Boat 5 / offered"), `reset to "The rescue" in ${r7.seconds} s: BR-199 offered to ${owner}`);
  await reset();
  const i7 = await integrity();
  check(i7.problems === 0, `after the drills and a final reset: integrity ${i7.problems}`);
} catch (e) {
  console.error(e);
  failed++;
} finally {
  await browser.close();
  say(failed ? `${failed} drill check(s) FAILED` : "all drills passed");
  process.exitCode = failed ? 1 : 0;
}
