# triage · rules set the priority, never the model

- **What it does:** `app/modules/triage/rules.py` turns a case's facts (hazards, needs, vulnerable people, headcount) into P1–P4 using the ordered rules in `rakshasetu.config.yaml` (`priority:`). The **highest** matching level wins, and the row shows **every** reason at that level ("P1 because: trapped + water/urgent medical · trapped + vulnerable person").
- **Key files:** `config/rakshasetu.config.yaml` (`priority`, `p1_order`), `app/core/expr.py` (the rule language), `cases.p1_rank`.
- **The tricky rule:** the rule language is tiny and safe: fact names from a fixed list, numbers, and/or/not, comparisons; parsed with Python's `ast` and walked by hand, never `eval`. A typo fails when the config loads. `medicine` (routine) ≠ `medical_urgent` (unconscious, not breathing, bleeding, labour). `buried`/`structure_collapsed` are P1, so a landslide isn't treated like a flood. Inside P1: infant or urgent medical → water rising → other vulnerable → longest wait.
- **When it runs:** on every new case, after a person corrects the facts, and after the language model back-fills (an officer's override, P1 #2, is left alone). A change is audited as `case.priority_changed` with from/to and why.
- **How to show it:** open the config in the editor; the demo case reads "P1 because: trapped + water/urgent medical"; an HP collapse is P1 "buried / collapse"; the injection line stays P4.


## Other disasters (added)
The closed hazard list also has `fire`, `smoke_gas`, `road_accident`, `earthquake` and `wind_damage`, read from Hindi,
Hinglish, Marathi and English words (`dictionaries/hi.yaml`). Rules, in `rakshasetu.config.yaml`:
- **P1:** fire or smoke/gas · a road accident with an injured or urgent-medical person · an earthquake with people
  trapped, buried, under a collapse or hurt.
- **P2:** a road accident, earthquake or storm damage on its own: worth a check, not an alarm.
- Inside P1, a spreading fire or gas ranks with rising water (`p1_rank`).

Dispatch: a **boat is required only for water** (`water_entering`, `water_rising`, `strong_current`, or a roof when
nothing else explains it). "Trapped" or "stranded" alone asks for nothing; fire and accidents set *preferred*
capabilities (`fire`, `medical`, `heavy_lift`). A team whose agency is Fire & Rescue counts as `fire` without a listing.
Tests: `tests/test_other_disasters.py` (no database).
