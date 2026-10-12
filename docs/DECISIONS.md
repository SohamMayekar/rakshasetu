# Decisions

*One paragraph per real decision, with the alternative we rejected. Newest last.*


### D2 · Base images from public.ecr.aws
Docker Hub returns 429 to anonymous pulls in the build sandbox (and venue NAT can trigger the same limit). The Dockerfiles use `public.ecr.aws/docker/library/{python,node,caddy}`, which mirror the official images for free with no account. PostGIS comes from `postgis/postgis` (not mirrored there). **Rejected:** Docker Hub defaults (rate-limited) and a paid registry (zero budget).

### D3 · Plain SQL migrations instead of Alembic; explicit SQL instead of an ORM
Migrations are numbered `.sql` files applied in order by `app/migrate.py` (≈40 lines) as `rakshasetu_owner`, tracked in `schema_migrations`; `grants.sql` is re-applied after every run. Queries use SQLAlchemy Core `text()` with explicit SQL, so every `WHERE` (including the `Scope`, rule R8) is visible in one place, and PostGIS calls (`ST_DWithin`, `ST_Distance`) are written as SQL rather than through GeoAlchemy2 types. **Rejected:** Alembic autogenerate and ORM models (more machinery for every member to explain; ORM queries hide where the scope filter sits).

### D4 · Two database roles; the demo reset is the only owner-level action outside migrations
`rakshasetu_app` (api, worker, ticker) owns no table and has INSERT + SELECT only on `events`, so the application cannot edit or delete history (tested: UPDATE/DELETE/TRUNCATE on `events` and CREATE TABLE are refused). `rakshasetu_owner` runs migrations. The demo reset must clear `events` and write a new genesis event, which the app role cannot do; it will run with owner credentials only when `DEMO_MODE=true` and only from the local listener. **Rejected:** granting TRUNCATE on `events` to the app role (it would let the app erase history silently in normal operation).

### D5 · Demo village: Thawe (Gopalganj), not a Muzaffarpur village
The PRD asked for a Muzaffarpur village whose temple and bridge are both in OSM within 500 m. Measured on the 12 Oct 2026 Bihar extract, Muzaffarpur has 26 mapped village points and 31 places of worship, and no village with a temple–bridge pair under 500 m (best: Sirsian, temple 648 m from the village, bridge 1,186 m from the temple). Thawe in Gopalganj has the village point 42 m from Thawe Durga Mata Mandir, a bridge 112 m from the temple, and no other place of worship within 1 km. The BR incident is "Bihar floods" with two districts, Gopalganj (live desk) and Muzaffarpur. **Rejected:** keeping Muzaffarpur with a fabricated or hand-placed landmark (dishonest), or a Muzaffarpur village with a single landmark (the circle would be 300 m Medium at best and the "temple + bridge" line wouldn't match the data). The humans should confirm this before rehearsal 1 (it changes one word in the pitch line).

### D6 · OSM source: openstreetmap.fr extract, because Overpass is unreachable here
Overpass (and its mirrors and Geofabrik) were unreachable from the build sandbox (the egress proxy drops the connection). The OSM editing API is reachable but its usage policy forbids read-only use (VERIFIED, operations.osmfoundation.org/policies/api). The openstreetmap.fr Bihar extract is an extract download service of the kind that policy recommends, so the gazetteer is built from it. `scripts/import_osm.py` keeps an Overpass mode for a laptop with open internet. **Rejected:** the editing API (policy), a hand-made fixture (not needed: real data was available).

### D7 · Seed cases are generated, with their ground truth beside them
`scripts/gen_seed_cases.py` builds 48 BR reports deterministically from structured choices and writes each choice as `truth`. Until the pipeline exists the loader uses `truth` directly (village-only Low circles, "not triaged yet"); once it exists, seeding runs the texts through the real pipeline and a test compares the pipeline's output with `truth`. **Rejected:** hand-written fields per case (drifts from the text, can't be measured).
