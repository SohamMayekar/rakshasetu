# The demo volunteer sheet (BR)

`volunteer_sheet.csv` is the sheet dropped on stage at 1:15 (PRD §16.1). It looks like what a relief desk gets from volunteers: Hinglish headers (`Naam`, `Mob No`, `Kitne log`, `Gaon`, `Samay`), names in Latin or Devanagari, phones written seven different ways, misspelt villages, blank cells, a volunteer's phone on eight families, and **14 phones already damaged by Excel** (`9.19877E+11`, `919877000000`).

`ground_truth.csv` says, for every row (Excel row number), which household it really is and what the import should do: `new`, `merged`, `to_check` or `history`.

| Kind | Rows | What it tests |
|---|---|---|
| `repeat2` / `repeat3` | 100 / 60 | the same household reported 2–3 times: same phone and landmark → **auto-merged** |
| `repeat_damaged_phone` | 8 | a repeat whose phone Excel damaged → **to check**, never merged |
| `damaged_phone` | 10 | single households with damaged phones → null, flagged, never identity |
| `relay_phone` | 8 | one volunteer's phone on 8 families → never identity |
| `das_pair` | 2 | Ramesh Das and Rajesh Das: same village, landmark, headcount → **refused** |
| `seeded_duplicate` | 4 | families already in the seed (`br-010`, `br-013`, `br-015`, `br-030`) → **to check** (village-only pins can't auto-merge, D10) |
| `no_location` | 3 | no village → **to check** |
| `old_report` | 3 | dated days before any demo run → **to check** ("old report: confirm before sending a team") |
| `needs_ai` | 19 | placed by rules but no headcount the rules can read → sent to the language model when one is configured |
| `done` | 8 | marked done/rescued/✓ → **closed history** |
| `single` | 75 | everyone else |

Regenerate with `make demo-sheet` (deterministic). Measure with `make sheet-eval` (results in `docs/MEASUREMENTS.md`).
All people and phone numbers are **synthetic** and never dialled; places are real OSM features (© OpenStreetMap contributors, ODbL). Thawe is left out on purpose: the live demo's household is there.
