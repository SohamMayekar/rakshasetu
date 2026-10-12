# demo · resets for a performed demo (no demo page)

- **What it is (m83):** there is no demo page in the app. The team performs the demo on the real screens ([`docs/DEMO.md`](../DEMO.md)); before it, and if anything goes wrong, `make demo-reset SCENE=<step>` restores the start of a step: the seed, then every earlier step replayed through the real API as the people who do it on stage (`app/modules/demo/scenes.py`, inputs in `data/scenarios/BR/demo.yaml`; D15). Every open screen reloads itself.
- **The API behind it** (`/v1/demo/*`, local listener only, DEMO_MODE only, the admin role, refused with a tunnel header; R18): `status`, `reset`, `play-clip` (the recorded clip through the reporter's own voice path, used by the replays and the golden path), `language-model` (on/off, for T10) and `surge` (the drills). Every call is an audit event.
- **Honesty:** the sidebar and the desk header say "demo data, clock 60× faster"; the recorded clip is a synthetic voice and is labelled so wherever it shows.
- **How to show it:** `make demo-reset SCENE=rescue`, then open the desk: the son's case is with Boat 5, waiting for the crew.
