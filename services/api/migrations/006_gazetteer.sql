-- 006 · the gazetteer (PRD §10, F-L4): real OSM places and landmarks for the live incident's districts,
-- imported once and committed (data/scenarios/BR/gazetteer). The location ladder only ever reads these rows.
CREATE TABLE places (
  id          bigserial PRIMARY KEY,
  incident_id bigint NOT NULL REFERENCES incidents(id),
  district_id bigint REFERENCES districts(id),
  name        text NOT NULL,
  name_hi     text,
  alt_names   text[] NOT NULL DEFAULT '{}',
  name_norm   text NOT NULL,              -- normalised Latin spelling used for fuzzy matching
  type        text NOT NULL,              -- village, hamlet, town, suburb, locality, ...
  geom        geography(Point, 4326) NOT NULL,
  radius_m    integer,
  osm_type    text,
  osm_id      bigint
);
CREATE INDEX places_geom_idx ON places USING gist (geom);
CREATE INDEX places_name_trgm_idx ON places USING gin (name_norm gin_trgm_ops);

CREATE TABLE landmarks (
  id          bigserial PRIMARY KEY,
  incident_id bigint NOT NULL REFERENCES incidents(id),
  district_id bigint REFERENCES districts(id),
  name        text,
  name_norm   text,
  type        text NOT NULL,              -- temple, mosque, bridge, school, hospital, water_tower, ...
  religion    text,
  detail      text,                       -- e.g. the road class a bridge carries
  geom        geography(Point, 4326) NOT NULL,
  osm_type    text,
  osm_id      bigint,
  part        integer NOT NULL DEFAULT 0  -- a long bridge is sampled along its length: same osm_id, several parts
);
CREATE INDEX landmarks_geom_idx ON landmarks USING gist (geom);
CREATE INDEX landmarks_type_idx ON landmarks (incident_id, type);

-- OSM district boundaries are multipolygons.
ALTER TABLE districts ALTER COLUMN boundary TYPE geography(MultiPolygon, 4326)
  USING CASE WHEN boundary IS NULL THEN NULL ELSE ST_Multi(boundary::geometry)::geography END;
