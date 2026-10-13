# telemetry

- **What it does:** a partner's instruments send signed readings (`POST /v1/ingest/telemetry`); each sensor is read against two lines (rising, danger); the desk's **Sensors** page shows the latest value, a trend and a state.
- **Key tables:** `sensors` (one per incident and code, created by its first reading) and `sensor_readings` (idempotent per sensor and key).
- **The tricky rule:** only a **change of state** is written to the audit chain, so a chatty sensor cannot bury the timeline; a reading never changes a case's priority.
- **How to show it:** `make telemetry-demo`, then open Sensors and History. Every demo sensor says **Simulated**.
- **Tests:** `tests/test_telemetry.py` (needs the database).
