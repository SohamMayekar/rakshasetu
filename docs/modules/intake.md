# intake · the one front door

- **What it does:** every channel adapter builds a **Canonical Report v1** and calls `accept()` (`app/modules/intake/service.py`). It inserts the report and its `report.process` job in **one transaction**, appends `report.received`, and returns the report id at once, before any AI runs.
- **Key tables:** `reports` (immutable; `UNIQUE (source_ns, idempotency_key)`), `jobs`.
- **The tricky rule:** the idempotency namespace comes from the **authenticated caller** (`user:7`, `partner:team-ai1`, `voice:<device>`), never from the body, so a retry returns the original id (`Idempotent-Replay: true`) and nobody can pre-claim another source's key.
- **Then:** the worker runs `report.process` (`app/pipeline/run.py`): network stages outside any transaction, then one short transaction that creates the case. A report that already has a case is left alone, so a re-delivered job can't make a second case.
- **How to show it:** the same `curl` twice → the same `report_id`, the second with `Idempotent-Replay: true` (Q&A security reel).
