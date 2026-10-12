# Tests

Run everything with `make test` (inside the api container, against the `rakshasetu_test` database).

- **Unit tests** sit next to each other in `tests/test_*.py`.
- **Scenario tests T1–T10** (PRD §13.6) live in `tests/scenarios/`, marked `@pytest.mark.scenario`. Each one drives the real API with seeded data.
- **Permission tests**: one per row of PRD §4.2, plus one IDOR test per resource (case, evidence, assignment, WS).
- **No fake clock** (cut list X18). A test that needs a deadline to pass moves it into the past with SQL, then runs the real ticker step.
- **No live provider calls.** Providers run in fixture mode (`PROVIDER_MODE=fixture`).
- **Never the demo database.** The harness points every engine at `rakshasetu_test`; the `seeded` fixture wipes and reseeds it.
