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
  forward: "Ramesh Das's family is in Thawe village, behind the Durga temple, near the bridge. 6 people are stuck on the roof, there is a lot of water.",
  das: "Rajesh Das, 5 people, Thawe village, near the temple, stuck on the roof" };
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

const O = await (await ctxOf(1366, 768)).newPage();          // the Duty officer, on the projector
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
  for (const name of ["Assignment", "Facts", "Timeline & evidence"]) await expand(name);   // the panel opens on its summary
}
// The case panel's sections start collapsed (m68): open one by its header, once.
async function expand(name) {
  const header = O.locator(`[data-section="${name}"] > button[aria-expanded="false"]`);
  if (await header.count()) await header.first().click();
}
// A button in the panel's summary, or under its "More" when it isn't the one next step.
async function drawerButton(name) {
  const b = drawer().getByRole("button", { name, exact: true });
  if (!(await b.isVisible().catch(() => false))) await drawer().getByRole("button", { name: "More", exact: true }).click();
  return b;
}

try {
  // ---- reset ---------------------------------------------------------------------------------------------------
  const r = await (await admin.post("/v1/demo/reset", { data: { scene: "son" } })).json();
  check(r.scene === "son" && r.seconds < 10, `demo reset to the start in ${r.seconds} s (< 10 s)`);
  await O.request.post(`${DESK}/v1/auth/login`, { data: { username: "rdas" } });
  await O.goto(`${DESK}/desk/BR`);
  await O.locator("ol[aria-label='Needs you now'] li").first().waitFor();
  say(`desk open as R. Das (Duty officer); son's voice: ${liveVoice ? "LIVE speech-to-text through the reporter page's microphone"
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
  check(/Urgent/.test(rowText) && /6 people/.test(rowText), `${pid} reads "Urgent · 6 people …": ${rowText.replace(/\n/g, " · ").slice(0, 90)}`);
  await shot(O, "01-desk-the-case-arrives");
  await shot(J, "01-phone-the-son");

  // ---- 0:25 the case, with receipts ----------------------------------------------------------------------------
  await open(pid);
  const facts = O.locator('[data-section="Facts"]');
  // let the drawer finish loading first (suggestions, timeline), so nothing shifts under the pointer
  await O.locator('[data-section="Assignment"] li').first().waitFor();
  await O.locator('[data-section="Timeline & evidence"]').getByText(/6 people/).first().waitFor();
  const lit = await until(async () => {
    await facts.getByText("6", { exact: true }).first().hover();
    return O.locator('[data-section="Timeline & evidence"] mark').first().innerText({ timeout: 300 });
  }, 8000);
  check(!!lit && /6/.test(lit), `hovering "6" lights up the son's own words: “${lit}”`);
  const factsText = await facts.innerText();
  check(/RULE|AI/.test(factsText), "every fact carries its method chip");
  const where = (await facts.innerText()).match(/because[^\n]*/)?.[0] ?? "";
  say(`the circle: ${where}`);
  const receipt = await O.locator('[data-section="Timeline & evidence"]').innerText();
  check(liveVoice ? /speech-to-text|stt/i.test(receipt) : receipt.includes("recorded transcript (not live speech to text)"),
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
  await (await drawerButton("Mark checked")).click();
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
  await O.getByRole("button", { name: "Add a sheet" }).click();
  await O.locator('input[type="file"]').setInputFiles(SCRIPT.sheet);
  await O.getByRole("button", { name: "Confirm mapping and import" }).click();
  const summary = await until(async () => (await O.locator('[aria-label="Import a sheet"]').innerText({ timeout: 300 })).match(/300 rows → [^\n]*/)?.[0], 90000);
  check(!!summary, `the sheet in ${((Date.now() - sheetStart) / 1000).toFixed(1)} s: “${summary}”`);
  await shot(O, "05-desk-the-volunteer-sheet");

  say("part 1 (0:00 → 1:45) done");

  // ---- 1:45 never stale ----------------------------------------------------------------------------------------
  await O.locator('[aria-label="Import a sheet"]').getByRole("button", { name: "Close" }).click().catch(() => {});
  await open(pid);
  const panel = O.locator('[data-section="Assignment"]');
  const pane = () => panel.innerText({ timeout: 300 });
  await until(async () => (await pane()).includes("Nearest suitable teams"), 10000);
  say(`dispatch suggests: ${(await panel.locator("li").first().innerText()).replace(/\n/g, " · ")}`);
  let boat2 = panel.locator("li", { hasText: "SDRF Boat 2" }).first();
  if (!(await boat2.isVisible())) { await panel.getByText(/^Other teams/).click(); boat2 = panel.locator("li", { hasText: "SDRF Boat 2" }).first(); }
  await boat2.getByRole("button", { name: "Send", exact: true }).click();
  check(!!(await until(async () => (await pane()).includes("Assigned to SDRF Boat 2"), 10000)), "the officer assigns SDRF Boat 2 (radio only)");
  await panel.getByRole("button", { name: "Heard on radio" }).click();
  await panel.getByRole("button", { name: "15 min" }).click();
  await panel.getByRole("button", { name: "Log contact" }).click();
  const acked = await until(async () => { const t = await pane(); return t.includes("ETA 15 min") && !t.includes("not accepted") && t; }, 10000);
  say(`assignment panel: ${String(acked).replace(/\n/g, " · ").slice(0, 300)}`);
  check(!!acked && acked.includes("ETA 15") && acked.includes("demo clock: 60× faster"), "\"Accepted on radio · VHF · ETA 15 min\"; the ring says the demo clock runs 60× faster");
  await shot(O, "06-desk-boat-2-acknowledged-on-radio");
  const quiet = Date.now();
  const overdue = await until(async () => (await pane()).match(/Contact overdue[^\n]*/)?.[0], 120000);
  check(!!overdue, `after ${((Date.now() - quiet) / 1000).toFixed(0)} s of silence (a 15 min ETA + grace, ×60): "${overdue}"`);
  check((await pane()).includes("Assigned to SDRF Boat 2"), "the case is still Boat 2's: nothing is taken away automatically");
  const esc = await until(async () => (await O.locator('[aria-label="Alerts"]').innerText({ timeout: 300 })).match(/SDRF Boat 2 overdue[^\n]*/)?.[0], 15000);
  check(!!esc, `one escalation for the officer: "${esc}"`);
  await shot(O, "07-desk-contact-overdue-the-case-stays");
  await panel.getByRole("button", { name: "Send another team", exact: true }).click();
  const boat5 = panel.locator("li", { hasText: "Fire & Rescue Boat 5" }).first();
  check(await boat5.isVisible(), "Fire & Rescue Boat 5 is among the suggestions to reassign to");
  await boat5.getByRole("button", { name: "Send this team" }).click();
  const moved = await until(async () => (await caption()).match(/moved from SDRF Boat 2 to Fire & Rescue Boat 5[^\n]*/)?.[0], 15000);
  check(!!moved, `reassigned by the officer: "${moved}"`);
  await shot(O, "08-desk-reassigned-to-boat-5");

  // ---- 2:30 the rescue -----------------------------------------------------------------------------------------
  const A = await (await ctxOf(390, 844)).newPage();           // the team lead of Fire & Rescue Boat 5
  await A.goto(`${PUBLIC}/responder`);
  await A.locator('input[name="u"]').fill("boat5");
  await A.locator('input[name="p"]').fill("rakshasetu");
  await A.getByRole("button", { name: "Sign in" }).click();
  const phone = () => A.locator("body").innerText({ timeout: 300 });
  const sent = async (label) => {
    const ok = !!(await until(async () => new RegExp(`${label}[^\\n]*Sent \\d`).test(await phone()), 30000));
    if (!ok) { say(`  the phone shows: ${(await phone()).replace(/\n/g, " | ").slice(0, 500)}`); await shot(A, "FAILED-team-phone"); }
    return ok;
  };
  async function trip(n, minus, left, label) {
    check(!!(await until(async () => /new case/i.test(await phone()) && (await phone()).includes(pid), 30000)),
          `trip ${n}: the team's phone shows a full-screen New case ${pid}`);
    if (n === 1) await shot(A, "09-phone-new-case");
    await A.getByRole("button", { name: "15 min" }).click();
    check(await sent("Accepted · ETA 15 min"), `trip ${n}: accepted, there in 15 min (saved on the phone, 10 s to undo, then sent)`);
    await A.goto(`${PUBLIC}/responder/case/${await caseId()}`);
    await A.getByRole("button", { name: /reached them/ }).click();
    check(await sent("Reached"), `trip ${n}: reached`);
    await A.getByRole("button", { name: /Record the rescue/ }).click();
    for (let i = 0; i < minus; i++) await A.getByRole("button", { name: "One fewer" }).click();
    await A.getByRole("button", { name: left ? "Yes" : "No", exact: true }).click();
    check(await sent(label), `trip ${n}: "${label}"`);
  }
  const caseId = async () => (await (await O.request.get(`${DESK}/v1/cases/${pid}`)).json()).id;
  await trip(1, 2, true, "Took 4 · someone still there");
  const back = await until(async () => { await showNew(); return (await row(pid).innerText({ timeout: 300 })).match(/2 of 6 still there/)?.[0]; }, 20000);
  check(!!back, `${pid} is back in the queue: "2 of 6 still there", with its original time`);
  await shot(O, "10-desk-2-of-6-still-there");
  await shot(A, "10-phone-rescue-sheet-sent");
  await open(pid);
  await until(async () => (await pane()).includes("Nearest suitable teams"), 10000);
  const top = await panel.locator("li").first().innerText();
  check(!top.includes("SDRF Boat 2"), `the silent Boat 2 isn't suggested again (stand-down not acknowledged); top: ${top.split("\n")[0]}`);
  await panel.locator("li", { hasText: "Fire & Rescue Boat 5" }).first().getByRole("button", { name: "Send", exact: true }).click()
    .catch(async () => { await panel.getByText(/^Other teams/).click(); await panel.locator("li", { hasText: "Fire & Rescue Boat 5" }).getByRole("button", { name: "Send", exact: true }).click(); });
  await A.goto(`${PUBLIC}/responder`);
  await trip(2, 0, false, "Rescued 2 · nobody left");
  const rescued = await until(async () => (await caption()).match(/^Rescued 6 of 6[^\n]*/)?.[0], 20000);
  check(!!rescued, `"${rescued}"`);

  // the family: only the phone that reported is asked, and need not answer
  await J.reload();
  const asked = await until(async () => (await J.locator("body").innerText({ timeout: 300 })).match(/The team says 6 people were rescued\. Is that right\?/)?.[0], 20000);
  check(!!asked, `the son's phone: "${asked} · You don't have to answer."`);
  await shot(J, "11-phone-the-family-is-asked");
  await J.getByRole("button", { name: "Yes", exact: true }).click();
  const thanked = await until(async () => (await J.locator("body").innerText({ timeout: 300 })).includes("Thank you"), 10000);
  const conf = await until(async () => (await caption()).startsWith("The family confirmed 6 rescued") && (await caption()), 15000);
  check(thanked && !!conf, `he taps Yes: "${conf}"`);
  await shot(O, "11-desk-confirmed-by-family");

  // ---- 3:05 the receipts ---------------------------------------------------------------------------------------
  await O.goto(`${DESK}/desk/BR?case=${pid}`);
  await drawer().waitFor();
  await expand("Timeline & evidence");
  const timeline = O.locator('[data-section="Timeline & evidence"]');
  await until(async () => (await timeline.innerText({ timeout: 300 })).includes("Rescue record"), 10000);
  const tl = await timeline.innerText();
  const good = (tl.match(/✓ unchanged since it was saved/g) ?? []).length, bad = (tl.match(/✗/g) ?? []).length;
  check(good >= 7 && bad === 0, `Timeline & evidence: ${good} items, each "✓ unchanged since it was saved" (its fingerprint matches the audit log) (the clip, its transcript, the forward, the merge, the radio log, two rescue records with where the team was)`);
  await timeline.scrollIntoViewIfNeeded();
  await shot(O, "12-desk-timeline-and-evidence");
  await O.goto(`${DESK}/audit`);
  await O.getByRole("button", { name: "Check nothing was changed" }).click();
  const verified = await until(async () => (await O.locator("main").innerText({ timeout: 300 })).match(/✓ [\d,]+ events verified/)?.[0], 20000);
  check(!!verified, `History → Check nothing was changed: "${verified}"`);
  await shot(O, "13-desk-chain-verified");
  const bar = await (await O.request.get(`${DESK}/v1/metrics/promises?incident=BR`)).json();
  check(bar.lost.adds_up && bar.lost.without_home === 0, `the promise bar adds up: ${bar.lost.reports} reports = ${bar.lost.cases} cases + ${bar.lost.merged} merged + ${bar.lost.to_check} to check + 0 without a home`);
  const integ = await (await O.request.get(`${DESK}/v1/integrity`)).json();
  check(integ.problems === 0, `integrity: ${integ.problems} problems (${integ.events_verified} events verified)`);
  // the team lead opens a case its team doesn't hold
  const other = (await (await O.request.get(`${DESK}/v1/queue?incident=BR`)).json()).rows.find((x) => x.kind === "case" && x.public_id !== pid);
  await A.goto(`${PUBLIC}/responder/case/${other.id}`);
  const denied = await until(async () => (await phone()).match(/Not assigned to your team/)?.[0], 10000);
  check(!!denied, `the team lead opens ${other.public_id}: 403 "${denied}"`);
  await shot(A, "14-phone-403-not-your-team");
  say("part 2 (1:45 → 3:05) done: the golden path ran end to end");
} catch (e) {
  await shot(O, "FAILED-desk").catch(() => {});
  await shot(J, "FAILED-phone").catch(() => {});
  console.error(e);
  process.exitCode = 1;
} finally {
  await browser.close();
}
