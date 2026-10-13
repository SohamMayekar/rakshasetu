# capabilities and teams

- **What it does:** one catalog of what a team can do (24 capabilities) and who teams are (20 agencies), used by dispatch and by the *Add a team* form (`GET /v1/teams/catalog`, `POST/PATCH /v1/teams`).
- **Key file:** `services/api/app/capabilities.py`; the ranking is in `app/modules/dispatch/service.py`.
- **The tricky rule:** a capability is *required* only where the job cannot be done without it (a boat for water, heavy lift for a collapse); everything else is *preferred*, so a team that lacks it is still offered and the officer decides. A Fire & Rescue agency counts as `fire` without listing it.
- **How to show it:** Teams → *Add a team*, tick a few capabilities, then send a team to a gas or accident report and see it lead the suggestions.
- **Tests:** `tests/test_capabilities.py`, `tests/test_other_disasters.py` (no database), `tests/test_team_management.py` (database).
