// How many things compete for attention on a screen (docs/SIMPLIFY_PLAN.md): the first view only, as a judge sees
// it before scrolling. Counts, at 1366×768 and at phone size:
//   controls = visible buttons, links, inputs, selects, text boxes and "show more" toggles
//   texts    = visible pieces of text outside those controls (each element with its own words: a label, a number, a line)
//
//   node e2e/count.mjs <spec> [<spec> ...]     (spec as in shoot.mjs: <path>[@<username>][#<name>][!<section>])
//   make count PAGES="/ /login /desk/BR@rdas"
//
// BASE (default http://127.0.0.1) is the local listener. Uses the pre-installed Chromium.

import { chromium } from "@playwright/test";

const specs = process.argv.slice(2);
if (!specs.length) { console.error("usage: node e2e/count.mjs <path>[@user][#name][!section] ..."); process.exit(2); }
const BASE = process.env.BASE ?? "http://127.0.0.1";
const SIZES = { desk: { width: 1366, height: 768 }, phone: { width: 390, height: 844 } };
const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY, bypass: "127.0.0.1,localhost" } : undefined;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/opt/pw-browsers/chromium", proxy });

function measure() {
  const W = window.innerWidth, H = window.innerHeight;
  const seen = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2 || r.bottom <= 0 || r.right <= 0 || r.top >= H || r.left >= W) return false;
    const s = getComputedStyle(el);
    return s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0.05;
  };
  const CONTROL = "button, a[href], input:not([type=hidden]), select, textarea, summary";
  const controls = [...document.querySelectorAll(CONTROL)].filter((el) => seen(el) && !el.closest(".maplibregl-ctrl, .maplibregl-ctrl-attrib"));
  const texts = [...document.querySelectorAll("body *")].filter((el) => {
    if (el.closest(CONTROL) || el.closest(".maplibregl-map") || ["SCRIPT", "STYLE", "svg", "path"].includes(el.tagName)) return false;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 0);
    return own && seen(el);
  });
  return { controls: controls.length, texts: texts.length };
}

for (const spec of specs) {
  const [, path, user, name, section] = spec.match(/^([^@#!]+)(?:@([^#!]+))?(?:#([^!]+))?(?:!(.+))?$/);
  const out = [];
  for (const [size, viewport] of Object.entries(SIZES)) {
    const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1, locale: "en-IN", timezoneId: "Asia/Kolkata" });
    const page = await ctx.newPage();
    if (user) await page.request.post(`${BASE}/v1/auth/login`, { data: { username: user } });
    await page.goto(BASE + path, { waitUntil: "networkidle" }).catch(() => page.goto(BASE + path));
    await page.waitForTimeout(Number(process.env.SETTLE_MS ?? 1500));
    if (section) {
      await page.evaluate((s) => document.querySelector(`[data-section="${s}"]`)?.scrollIntoView({ block: "start" }), section);
      await page.waitForTimeout(400);
    }
    const m = await page.evaluate(measure);
    out.push(`${size} ${m.controls} controls + ${m.texts} texts = ${m.controls + m.texts}`);
    await ctx.close();
  }
  console.log(`${(name ?? path).padEnd(28)} ${user ? `(${user})`.padEnd(9) : "".padEnd(9)} ${out.join(" · ")}`);
}
await browser.close();
