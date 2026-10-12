# Decisions

*One paragraph per real decision, with the alternative we rejected. Newest last.*


### D2 · Base images from public.ecr.aws
Docker Hub returns 429 to anonymous pulls in the build sandbox (and venue NAT can trigger the same limit). The Dockerfiles use `public.ecr.aws/docker/library/{python,node,caddy}`, which mirror the official images for free with no account. PostGIS comes from `postgis/postgis` (not mirrored there). **Rejected:** Docker Hub defaults (rate-limited) and a paid registry (zero budget).

### D3 · Plain SQL migrations instead of Alembic; explicit SQL instead of an ORM
Migrations are numbered `.sql` files applied in order by `app/migrate.py` (≈40 lines) as `rakshasetu_owner`, tracked in `schema_migrations`; `grants.sql` is re-applied after every run. Queries use SQLAlchemy Core `text()` with explicit SQL, so every `WHERE` (including the `Scope`, rule R8) is visible in one place, and PostGIS calls (`ST_DWithin`, `ST_Distance`) are written as SQL rather than through GeoAlchemy2 types. **Rejected:** Alembic autogenerate and ORM models (more machinery for every member to explain; ORM queries hide where the scope filter sits).

### D4 · Two database roles; the demo reset is the only owner-level action outside migrations
`rakshasetu_app` (api, worker, ticker) owns no table and has INSERT + SELECT only on `events`, so the application cannot edit or delete history (tested: UPDATE/DELETE/TRUNCATE on `events` and CREATE TABLE are refused). `rakshasetu_owner` runs migrations. The demo reset must clear `events` and write a new genesis event, which the app role cannot do; it will run with owner credentials only when `DEMO_MODE=true` and only from the local listener. **Rejected:** granting TRUNCATE on `events` to the app role (it would let the app erase history silently in normal operation).
