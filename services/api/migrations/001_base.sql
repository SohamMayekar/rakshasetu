-- 001 · base schema (PRD §10). Runs as rakshasetu_owner. Geometry is geography(Point, 4326).

CREATE TABLE incidents (
  id               bigserial PRIMARY KEY,
  code             text NOT NULL UNIQUE CHECK (code ~ '^[A-Z]{2,4}$'),   -- BR, OD, HP
  name             text NOT NULL,
  type             text NOT NULL,                                      -- flood, cyclone, landslide, ...
  states           text[] NOT NULL DEFAULT '{}',
  language         text NOT NULL DEFAULT 'hi',
  center           geography(Point, 4326),
  region           geography(Polygon, 4326),
  status           text NOT NULL DEFAULT 'active'
                   CHECK (status IN ('draft', 'active', 'standing_down', 'closed')),
  next_case_number integer NOT NULL DEFAULT 1,                         -- BR-214 numbering
  created_at       timestamptz NOT NULL DEFAULT now(),
  closed_at        timestamptz
);

CREATE TABLE districts (
  id          bigserial PRIMARY KEY,
  incident_id bigint NOT NULL REFERENCES incidents(id),
  name        text NOT NULL,
  state       text NOT NULL,
  centroid    geography(Point, 4326) NOT NULL,
  boundary    geography(Polygon, 4326),
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (incident_id, name)
);

CREATE TABLE teams (
  id              bigserial PRIMARY KEY,
  incident_id     bigint NOT NULL REFERENCES incidents(id),
  district_id     bigint NOT NULL REFERENCES districts(id),
  name            text NOT NULL,                                       -- "SDRF Boat 2"
  agency          text NOT NULL CHECK (agency IN
                  ('NDRF', 'SDRF', 'Fire & Rescue', 'Police', 'Aapda Mitra', 'Fishermen', 'NGO')),
  capabilities    text[] NOT NULL DEFAULT '{}',                        -- boat, medical, rope, heavy_lift
  has_app         boolean NOT NULL DEFAULT true,                       -- false: radio-only team
  radio_channel   text,                                                -- VHF, HAM, satellite, phone
  base_geom       geography(Point, 4326),
  last_geom       geography(Point, 4326),
  last_geom_at    timestamptz,                                         -- "position 20 min old"
  max_active      integer NOT NULL DEFAULT 2,
  status          text NOT NULL DEFAULT 'available'
                  CHECK (status IN ('available', 'assigned', 'overdue', 'out_of_service')),
  status_reason   text,
  last_contact_at timestamptz,                                         -- deliberate contact only
  last_seen_at    timestamptz,                                         -- app heartbeat: display only
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (incident_id, name)
);

CREATE TABLE users (
  id            bigserial PRIMARY KEY,
  username      text NOT NULL UNIQUE,
  name          text NOT NULL,
  role          text NOT NULL CHECK (role IN
                ('call_taker', 'duty_officer', 'incharge', 'team_lead', 'seoc_viewer', 'admin')),
  incident_ids  bigint[] NOT NULL DEFAULT '{}',
  district_ids  bigint[] NOT NULL DEFAULT '{}',
  team_id       bigint REFERENCES teams(id),
  password_hash text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cases (
  id                        bigserial PRIMARY KEY,
  public_id                 text NOT NULL UNIQUE,                       -- BR-214
  incident_id               bigint NOT NULL REFERENCES incidents(id),
  district_id               bigint REFERENCES districts(id),
  status                    text NOT NULL DEFAULT 'reported' CHECK (status IN
                            ('reported', 'checked', 'assigned', 'acknowledged', 'reached',
                             'rescued', 'closed', 'merged', 'cancelled')),
  priority                  text NOT NULL DEFAULT 'P4' CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
  priority_reasons          text[] NOT NULL DEFAULT '{}',
  priority_override         jsonb,                                      -- P1 #2: {level, by, reason}
  people_count              integer,
  people_count_kind         text CHECK (people_count_kind IN ('stated', 'estimated')),
  people_remaining          integer,
  needs                     text[] NOT NULL DEFAULT '{}',
  vulnerable                text[] NOT NULL DEFAULT '{}',
  hazards                   text[] NOT NULL DEFAULT '{}',
  geom                      geography(Point, 4326),
  radius_m                  integer,
  location_confidence       text CHECK (location_confidence IN ('high', 'medium', 'low', 'very_low')),
  location_method           text,                                       -- the method sentence
  location_source           text CHECK (location_source IN ('ai', 'rule', 'human', 'gps')),
  location_text             text,
  provenance                jsonb NOT NULL DEFAULT '{}',                -- per field: value, method, quote, report, checked_by, at
  summary                   text,                                       -- template line, never LLM prose
  credibility               text,
  checked_by                bigint REFERENCES users(id),
  checked_at                timestamptz,
  last_confirmed_at         timestamptz,
  onsite_contact_phone_enc  text,
  onsite_contact_phone_hash text,
  parent_case_id            bigint REFERENCES cases(id),                -- the case this one was merged into
  queue_since               timestamptz NOT NULL DEFAULT now(),         -- partial rescues keep the original
  is_demo_live              boolean NOT NULL DEFAULT false,             -- short demo timers apply only to these
  resolution                text,
  escalation_level          integer NOT NULL DEFAULT 0,
  flags                     text[] NOT NULL DEFAULT '{}',
  attributes                jsonb NOT NULL DEFAULT '{}',                -- new fields without a migration (§15)
  version                   integer NOT NULL DEFAULT 1,                 -- optimistic lock (If-Match)
  created_at                timestamptz NOT NULL DEFAULT now(),
  updated_at                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX cases_geom_idx ON cases USING gist (geom);
CREATE INDEX cases_incident_status_idx ON cases (incident_id, status);

CREATE TABLE reports (
  id                    bigserial PRIMARY KEY,
  incident_id           bigint REFERENCES incidents(id),
  channel               text NOT NULL CHECK (channel IN ('voice', 'whatsapp', 'web_form', 'spreadsheet', 'partner')),
  schema_version        text NOT NULL DEFAULT '1',
  source_ns             text NOT NULL,                                  -- set from the authenticated caller (R4)
  idempotency_key       text NOT NULL,
  received_at           timestamptz NOT NULL DEFAULT now(),
  original_reported_at  timestamptz,
  reporter_phone_enc    text,
  reporter_phone_hash   text,
  reporter_phone_masked text,
  device_hash           text,
  reporter_name         text,
  reporter_relation     text NOT NULL DEFAULT 'unknown',
  is_forward            boolean NOT NULL DEFAULT false,
  text_sha256           text,
  language              text,
  text                  text,                                           -- immutable: never edited
  transcript            text,
  structured            jsonb,                                          -- pre-extracted fields (partners, surge)
  extraction            jsonb,
  extraction_method     text CHECK (extraction_method IN ('ai', 'rules', 'structured')),
  receipt               jsonb NOT NULL DEFAULT '[]',                    -- pipeline receipt steps
  status                text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processed', 'needs_review', 'merged')),
  review_reason         text,
  case_id               bigint REFERENCES cases(id),
  source                jsonb NOT NULL DEFAULT '{}',
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_ns, idempotency_key)
);
CREATE INDEX reports_phone_hash_idx ON reports (reporter_phone_hash) WHERE reporter_phone_hash IS NOT NULL;
CREATE INDEX reports_device_hash_idx ON reports (device_hash) WHERE device_hash IS NOT NULL;
CREATE INDEX reports_case_idx ON reports (case_id);

-- The audit trail AND the real-time stream (rule R1). Append-only, hash-chained:
-- hash = sha256(prev_hash || body), body = canonical JSON text generated once.
CREATE TABLE events (
  seq         bigint PRIMARY KEY,
  at          timestamptz NOT NULL,
  actor_type  text NOT NULL CHECK (actor_type IN ('user', 'system', 'partner', 'reporter')),
  actor_id    text,
  actor_role  text,
  action      text NOT NULL,
  entity_type text NOT NULL,
  entity_id   text,
  incident_id bigint,
  district_id bigint,
  case_id     bigint,
  team_id     bigint,
  body        text NOT NULL,
  reason      text,
  prev_hash   text NOT NULL,
  hash        text NOT NULL UNIQUE
);
CREATE INDEX events_case_idx ON events (case_id, seq);
CREATE INDEX events_incident_idx ON events (incident_id, seq);
