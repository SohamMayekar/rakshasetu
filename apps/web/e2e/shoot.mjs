// Screenshots for review: every page at the projector size (1366×768) and a phone (390×844).
//
//   node e2e/shoot.mjs <out-dir> <spec> [<spec> ...]
//   spec = <path>[@<username>][#<name>]      e.g.  /ui#design-system   /desk/BR@priya#desk
//
// BASE (default http://127.0.0.1) is the LOCAL listener, as on the projector. Uses the pre-installed Chromium.

import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "@playwright/test";

const [out, ...specs] = process.argv.slice(2);
if (!out || !specs.length) {
  console.error("usage: node e2e/shoot.mjs <out-dir> <path>[@user][#name] ...");
  process.exit(2);
}
const BASE = process.env.BASE ?? "http://127.0.0.1";
const SIZES = { desk: { width: 1366, height: 768 }, phone: { width: 390, height: 844 } };
mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/opt/pw-browsers/chromium" });
for (const spec of specs) {
  const [, path, user, name] = spec.match(/^([^@#]+)(?:@([^#]+))?(?:#(.+))?$/);
  const label = name ?? (path.replace(/\W+/g, "-").replace(/^-|-$/g, "") || "home");
  for (const [size, viewport] of Object.entries(SIZES)) {
    const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1, locale: "en-IN", timezoneId: "Asia/Kolkata" });
    const page = await ctx.newPage();
    if (user) {
      const r = await page.request.post(`${BASE}/v1/auth/login`, { data: { username: user } });
      if (!r.ok()) throw new Error(`login ${user}: ${r.status()} ${await r.text()}`);
    }
    await page.goto(BASE + path, { waitUntil: "networkidle" }).catch(() => page.goto(BASE + path));
    await page.waitForTimeout(Number(process.env.SETTLE_MS ?? 1200));
    const file = join(out, `${label}-${size}.png`);
    await page.screenshot({ path: file, fullPage: false });
    console.log(file);
    await ctx.close();
  }
}
await browser.close();
