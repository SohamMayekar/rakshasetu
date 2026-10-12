# Design audit (m78–m82)

*12 Oct 2026. A visual pass only: no feature, no rule and no wording of promises changes. Read against the public design skills the team pointed to, as reference: Anthropic's frontend-design; Vercel's web interface guidelines; taste-skill's redesign and minimalist variants; Bencium's design-audit and controlled UX designer. Where they disagree with CLAUDE.md, CLAUDE.md wins: Noto Sans stays (Devanagari), colour means priority only, lucide stays.*

## What the app is, in one line
A control-room tool for families stranded in a flood, used under stress on a projector and on wet phones. So: calm, dense where it must be, one obvious action per screen, nothing decorative.

## Findings, by phase

### Phase 1: foundations (m78)
| Finding | Fix |
|---|---|
| 13 different text sizes in pixels (`text-[13px]`, `[15px]`, `[17px]`, `[22px]`, `[26px]`, `[28px]`…) | A six-step type scale as tokens: display 32, title 22, heading 17, body 15, small 13, micro 11; every screen uses only these |
| Three card radii (20, 24, 28 px) next to 16 and 12 | One rule: card 16, well/row/input 12, buttons and chips pill |
| Neutral grey shadows on a warm canvas | Shadows tinted toward the canvas, used only on surfaces that float |
| No visible keyboard focus on most controls | `:focus-visible` ink outline everywhere |
| Buttons have no pressed feedback; transitions animate everything | `active:scale-[0.98]`, explicit transition properties, `prefers-reduced-motion` honoured |
| All-caps tracked labels ("NEW CASE", "HOW THE FIRST ROWS READ", the AI/RULE chips) | Sentence case at the small size |
| `h-screen` / `min-h-screen` jump on phone browsers | `dvh` units; `viewport-fit=cover` |
| Double-tap zoom delay and grey tap flash on phones | `touch-action: manipulation`, no tap highlight |

### Phase 2: the desk (m79)
- The three numbers don't line up with the columns under them; the header, numbers and columns use different gutters.
- Row anatomy varies: the second line truncates into "BR-3…" when the button is long; buttons sit at different x positions.
- Every block is a white card with a shadow, including the map; elevation stops meaning anything.

### Phase 3: the case panel (m80)
- The summary, the sections and the assignment block compete at the same weight.
- The four sections read as a list of headers with chevrons; their hints wrap unevenly.
- Facts use a fixed 92 px label column that clips longer values.

### Phase 4: phones (m81)
- No safe-area padding on the team app's bottom actions or the reporter's footer.
- The team's next action can scroll out of view on the case screen.
- Touch targets under 44 px in places (Undo, links styled as text).

### Phase 5: the other pages and release (m82)
- Front door, sign-in, All incidents, History, Demo and the load screen use different widths and header spacing.
- History's table has no sticky header and heavy row lines.

## Rules kept from CLAUDE.md that override the references
Noto Sans (incl. Devanagari) with tabular figures; hue only for priority, always with a word and a shape; lucide icons at one stroke width (1.8); no toasts or modals for events; the list never re-sorts under the cursor; responder buttons ≥ 64 px.
