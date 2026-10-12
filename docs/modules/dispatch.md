# dispatch · which team, and why (an officer decides)

- **What it does:** `GET /v1/cases/{ref}/dispatch` ranks the teams **already deployed in the case's district** (`app/modules/dispatch/`). Described on stage as standard practice — 112's CAD does nearest-unit dispatch — not as innovation.
- **The ranking (deterministic):** capability match first (a **boat** for people trapped by water, **heavy lift** for a collapse; **medical** preferred for an urgent medical need), then **straight-line distance** from the team's last known position, then current load. Ties break on the team id, so the same inputs always give the same list (tested).
- **Every line says why:** "2.1 km straight-line · position 20 min old · boat, rope · 0 active · radio only (VHF)". A team without what's needed says so ("no boat"). A case with no pin says "distance unknown (no pin)".
- **Never suggested, shown greyed with the reason:** out of service ("Out of service · refuelling"), **contact overdue** ("greyed until heard from"), or at capacity ("at capacity (2 of 2)").
- **On the desk:** an officer's queue row carries the top suggestion as its button: **"Assign → NDRF T-03 (deployed) · 4.0 km · boat, medical"**. The officer assigns; nothing is assigned automatically (m40).
