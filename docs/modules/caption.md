# caption · one plain sentence for the judges (DEMO_MODE)

- **What it does:** on the **projector desk only** (local listener, DEMO_MODE on), a dark line at the bottom of the screen says, in one sentence, the most important thing that just happened and why. It shows for 9 s. It is built from the live event frames the desk already receives (`apps/web/lib/caption.ts`); there is no extra server path.
- **Template-based, never a model.** Every sentence is a template over the event's own data: the same reason lines the timeline and the merge table use. It says what the **rules or a person** did. When the language model read a report, the caption doesn't speak for it: it says "Rules set the priority; every fact keeps its quote".
- **Examples** (measured in Chromium on the demo spine, 12 Oct 2026):
  - "The recorded clip (a synthetic voice) became BR-199, P1 because trapped + water/urgent medical · trapped + vulnerable person. Rules set the priority; every fact keeps its quote."
  - "BR-200 is likely the same household as BR-199: same village (Thawe) · circles overlap (0 m apart) · same landmarks (Thawe durga mata mandir, bridge) · same headcount (6) · 0 min apart. A person decides."
  - "BR-201 was not merged with BR-199: Rajesh ≠ Ramesh. Village and headcount alone are weak."
  - "SDRF Boat 2 now owns BR-199. Its timer runs on the demo clock ×60. Nobody else is sent unless an officer decides."
  - "The language model is off. Reports still become cases: the keyword rules read them, and the chips say Rule."
- **One per frame, by importance:** a reset, the demo switches, a finished sheet, rescue outcomes, reassignment, overdue, refusals, merges, suggestions, new cases, contact and assignments, then the rest. Surge reports and sheet rows are never captioned one by one: a surge frame reads "Surge: 50 synthetic reports in the last second. The list holds still; new rows wait behind the pill", and a sheet is captioned by its progress and its summary line.
- **Memory across frames:** a voice report's case is made about a second after the report arrives, and a new case's suggestion can arrive before the desk has loaded that case. So the caption remembers report channels, clip report ids and new case numbers. Each is bounded to 500 entries.
- **Not shown:** on the public listener, outside DEMO_MODE, on phones, and on any screen but the desk.
