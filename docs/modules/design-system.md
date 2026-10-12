# design system · ink on paper, hue = priority

- **What it is:** `apps/web/components/ui/` — the small set of pieces every screen is built from, shown together at **`/ui`** (local listener only). Tokens live in `app/globals.css` (`@theme`): ink, three greys, one hairline, paper, the four priority hues, and amber.
- **The rules it encodes (PRD §13.5):** **hue means priority and nothing else**, and every priority is also text and a shape (`▲ P1 · ◆ P2 · ● P3 · ○ P4`); "needs you" is **ink inversion** (the attention chip); stale is **fade** (`.stale`); uncertainty is shown — `~6` estimates, `○` unchecked, **amber ○** only where the quote check failed (F-C13), dashed circle = Low.
- **Receipts:** `MethodChip` (AI · Rule · Human · Partner · Fixture; AI in italics), `Check` (● / ○ / amber ○), `ChannelTag` (VOICE · WA · SHEET · DESK · API) and `Receipt`, the grey pipeline line under each report.
- **Because:** `Because` renders the reason line every decision carries ("because trapped + water entering").
- **Field buttons** (`size="field"`) are ≥ 64 px tall and full width, for the responder and reporter screens.
- **Caption:** the judge-legibility line (DEMO_MODE), one plain sentence from a template; it never speaks for the model.
