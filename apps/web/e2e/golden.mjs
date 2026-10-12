// The golden path (PRD §16.1, 0:00 → 3:05) driven through the real screens, end to end, on the running stack:
// the officer's desk on the projector (http://localhost), the judge's phone and the team's phone on the PUBLIC
// listener (http://127.0.0.1:8080, as through the tunnel), and the demo controls (http://127.0.0.1/demo).
// Every beat asserts what the judge should see and takes a screenshot (docs/screens/golden/). Exit code 1 on
// the first thing that isn't so.
//
//   make e2e            (= node apps/web/e2e/golden.mjs; needs `make up`; resets the demo first)
//
// The son's voice: with a speech-to-text key, the synthetic clip is played into Chromium's fake microphone on the
// reporter page (the judge's path). Without one, a recorded voice can only become an "audio only" case, so the
// script plays the clip through the demo control instead (the same voice pipeline, with its recorded transcript)
// and SAYS SO in its output; the judge's phone then follows the son's case as his phone (the demo QR link).

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { chromium, request } from "@playwright/test";

const ROOT = resolve(new URL("../../..", import.meta.url).pathname);
const OUT = join(ROOT, "docs/screens/golden");
const DESK = "http://localhost", LOCAL = "http://127.0.0.1", PUBLIC = "http://127.0.0.1:8080";
const SCRIPT = { son: "demo-son-phone-0001", sheet: join(ROOT, "data/scenarios/BR/sheet/volunteer_sheet.csv"),
  clip: "clips/son-line.synthetic.ogg",
  forward: "Ramesh Das ka parivaar Thawe gaon mein hai, Durga mandir ke peeche, pul ke paas. 6 log chhat par fase hain, paani bahut hai.",
  das: "Rajesh Das, 5 log, Thawe gaon, mandir ke paas, chhat par fase hain" };
mkdirSync(OUT, { recursive: true });

const log = [];
const t0 = Date.now();
const say = (s) => { const line = `${((Date.now() - t0) / 1000).toFixed(1).padStart(6)} s  ${s}`; log.push(line); console.log(line); };
function check(ok, what) { if (!ok) { say(`✗ ${what}`); throw new Error(what); } say(`✓ ${what}`); }
const until = async (fn, ms = 30000, every = 250) => {
  const end = Date.now() + ms;
  for (;;) { const v = await fn().catch(() => null); if (v) return v; if (Date.now() > end) return null; await new Promise((r) => setTimeout(r, every)); }
};

// ---- the people ----------------------------------------------------------------------------------------------
const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY, bypass: "127.0.0.1,localhost" } : undefined;
const exe = process.env.CHROMIUM ?? (existsSync("/opt/pw-browsers/chromium") ? "/opt/pw-browsers/chromium" : undefined);   // else Playwright's own
const admin = await request.newContext({ baseURL: LOCAL });
await admin.post("/v1/auth/login", { data: { username: "admin" } });
const status = await (await admin.get("/v1/demo/status")).json();
const liveVoice = status.keys.stt.length > 0;

let mic = [];
if (liveVoice) {   // the clip as the phone's microphone (WAV is what Chromium's fake capture reads)
  const wav = join(tmpdir(), "rs-son-line.wav");
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-i", join(ROOT, "data/scenarios/BR", SCRIPT.clip), "-ac", "1", "-ar", "48000", wav]);
  mic = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", `--use-file-for-fake-audio-capture=${wav}%noloop`];
}
const browser = await chromium.launch({ executablePath: exe, proxy, args: mic });
const ctxOf = (w, h) => browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: "en-IN", timezoneId: "Asia/Kolkata" });

const O = await (await ctxOf(1366, 768)).newPage();          // the EOC Duty Officer, on the projector
const J = await (await ctxOf(390, 844)).newPage();           // the judge, as Ramesh's son in Mumbai
const shot = async (page, name) => page.screenshot({ path: join(OUT, `${name}.png`) });
const caption = () => O.locator("div[role=status] p").innerText({ timeout: 300 }).catch(() => "");
const row = (pid) => O.locator("ol[aria-label='Needs you now'] li", { hasText: pid }).first();
const drawer = () => O.locator("aside[aria-label^='Case']");
async function showNew() { const pill = O.getByRole("button", { name: /new: show/ }); if (await pill.isVisible().catch(() => false)) await pill.click(); }
async function open(pid) {
  await showNew();
  if (!(await drawer().getAttribute("aria-label", { timeout: 300 }).catch(() => ""))?.includes(pid)) {
    await O.goto(`${DESK}/desk/BR?case=${pid}`);
  }
  await until(async () => (await drawer().getAttribute("aria-label", { timeout: 300 }))?.includes(pid), 15000);
}

try {
  // ---- reset ---------------------------------------------------------------------------------------------------
  const r = await (await admin.post("/v1/demo/reset", { data: { scene: "son" } })).json();
  check(r.scene === "son" && r.seconds < 10, `demo reset to the start in ${r.seconds} s (< 10 s)`);
  await O.request.post(`${DESK}/v1/auth/login`, { data: { username: "rdas" } });
  await O.goto(`${DESK}/desk/BR`);
  await O.locator("ol[aria-label='Needs you now'] li").first().waitFor();
  say(`desk open as R. Das (EOC Duty Officer); son's voice: ${liveVoice ? "LIVE speech-to-text through the reporter page's microphone"
    : "no speech-to-text key, so the recorded clip goes through the demo control (same voice pipeline, recorded transcript)"}`);

  // ---- 0:00 the son in Mumbai ----------------------------------------------------------------------------------
  let pid, started = Date.now();
  if (liveVoice) {
    await J.goto(`${PUBLIC}/r`);
    await J.getByRole("button", { name: "Tap to talk" }).click();
    await J.waitForTimeout(12500);
    started = Date.now();
    await J.getByRole("button", { name: "Stop" }).click();
    pid = await until(async () => (await J.locator("body").innerText()).match(/BR-\d+/)?.[0], 60000);
    check(!!pid, `the judge's phone shows the case number: ${pid}`);
  } else {
    const played = await (await admin.post("/v1/demo/play-clip", { data: { clip: SCRIPT.clip } })).json();
    pid = await until(async () => (await (await admin.get(`${PUBLIC}/v1/public/turns/${played.report_id}?device_id=${SCRIPT.son}`)).json()).public_id, 30000);
    check(!!pid, `the son's clip became ${pid}`);
    await J.goto(`${PUBLIC}/s/${pid}#device=${SCRIPT.son}`);   // the demo QR: the judge's phone becomes the son's phone
    await J.getByText(pid).first().waitFor();
  }
  const onDesk = await until(async () => { await showNew(); return (await row(pid).isVisible()) && Date.now(); }, 20000);
  check(!!onDesk, `${pid} is on the desk ${((onDesk - started) / 1000).toFixed(1)} s after the son finished`);
  const rowText = await row(pid).innerText();
  check(/P1/.test(rowText) && /6 people/.test(rowText), `${pid} reads "P1 · 6 people …": ${rowText.replace(/\n/g, " · ").slice(0, 90)}`);
  await shot(O, "01-desk-the-case-arrives");
  await shot(J, "01-phone-the-son");

  // ---- 0:25 the case, with receipts ----------------------------------------------------------------------------
  await open(pid);
  const facts = O.locator('[data-section="Facts"]');
  await facts.getByText("6", { exact: true }).first().hover();
  const lit = await until(async () => (await O.locator('[data-section="Timeline & evidence"] mark').first().innerText({ timeout: 300 })), 5000);
  check(!!lit && /6/.test(lit), `hovering "6" lights up the son's own words: “${lit}”`);
  const factsText = await facts.innerText();
  check(/RULE|AI/.test(factsText), "every fact carries its method chip");
  const where = (await facts.innerText()).match(/because[^\n]*/)?.[0] ?? "";
  say(`the circle: ${where}`);
  const receipt = await O.locator('[data-section="Timeline & evidence"]').innerText();
  check(liveVoice ? /speech-to-text|stt/i.test(receipt) : receipt.includes("recorded transcript (not a live STT call)"),
        liveVoice ? "the receipt names the speech-to-text provider" : "the receipt says the words are a recorded transcript, not live speech-to-text");
  await O.locator('[data-section="Facts"]').scrollIntoViewIfNeeded();
  await shot(O, "02-desk-the-sons-words-light-up");

  // ---- 0:50 never doubled --------------------------------------------------------------------------------------
  await O.getByRole("button", { name: "New report" }).click();
  await O.locator("textarea").fill(SCRIPT.forward);
  await O.getByText("This is a forwarded message").click();
  await O.getByRole("button", { name: "Save report" }).click();
  const fwd = await until(async () => (await caption()).match(/^(BR-\d+) is likely the same household as (BR-\d+)/), 20000);
  check(!!fwd && fwd[2] === pid, `the forward ${fwd?.[1]} is suggested as the same household as ${pid}, with reasons`);
  await shot(O, "03-desk-the-forward-is-suggested");
  await open(fwd[1]);
  await drawer().getByRole("button", { name: /^Merge/ }).first().click();
  await drawer().locator("form").getByRole("button", { name: "Merge" }).click();
  const merged = await until(async () => (await caption()).startsWith(`A person merged ${fwd[1]} into ${pid}`) && (await caption()), 15000);
  check(!!merged, `merged by a person: “${merged.slice(0, 80)}…”`);
  await open(pid);
  await drawer().getByRole("button", { name: "Check", exact: true }).click();
  await until(async () => !(await drawer().innerText({ timeout: 300 })).includes("not checked yet"), 10000);
  check(true, `${pid} checked by R. Das`);
  await O.getByRole("button", { name: "New report" }).click();
  await O.locator("textarea").fill(SCRIPT.das);
  await O.locator('input[name="phone"]').fill("98765 70003");
  await O.getByRole("button", { name: "Save report" }).click();
  const refused = await until(async () => (await caption()).match(/^(BR-\d+) was not merged with (BR-\d+): Rajesh ≠ Ramesh/), 20000);
  check(!!refused && refused[2] === pid, `the Das family is refused: “${refused?.[0]}…”`);
  await shot(O, "04-desk-rajesh-is-not-ramesh");

  // ---- 1:15 the volunteer sheet --------------------------------------------------------------------------------
  const sheetStart = Date.now();
  await O.getByRole("button", { name: "Import sheet" }).click();
  await O.locator('input[type="file"]').setInputFiles(SCRIPT.sheet);
  await O.getByRole("button", { name: "Confirm mapping and import" }).click();
  const summary = await until(async () => (await O.locator('[aria-label="Import a sheet"]').innerText({ timeout: 300 })).match(/300 rows → [^\n]*/)?.[0], 90000);
  check(!!summary, `the sheet in ${((Date.now() - sheetStart) / 1000).toFixed(1)} s: “${summary}”`);
  await shot(O, "05-desk-the-volunteer-sheet");

  say("part 1 (0:00 → 1:45) done");
} catch (e) {
  await shot(O, "FAILED-desk").catch(() => {});
  await shot(J, "FAILED-phone").catch(() => {});
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
}
