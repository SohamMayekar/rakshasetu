-- 020 · telemetry (the brief's "IoT supplies live telemetry"): a partner's sensors report numbers. A sensor
-- is registered by its first reading and read against two thresholds. Only a change of state (ok → warn →
-- danger) is written to the audit chain; every reading is kept here. `simulated` is stated on every screen:
-- the demo's sensors are our own script, never presented as real instruments.
CREATE TABLE sensors (
  id           bigserial PRIMARY KEY,
  incident_id  bigint NOT NULL REFERENCES incidents(id),
  district_id  bigint REFERENCES districts(id),
  code         text NOT NULL,
  name         text NOT NULL,
  kind         text NOT NULL DEFAULT 'other',      -- water_level, rainfall, wind, temperature, other
  unit         text NOT NULL DEFAULT '',
  geom         geography(Point, 4326),
  warn_at      double precision,
  danger_at    double precision,
  partner      text,
  simulated    boolean NOT NULL DEFAULT false,
  state        text NOT NULL DEFAULT 'unknown' CHECK (state IN ('unknown', 'ok', 'warn', 'danger')),
  last_value   double precision,
  last_read_at timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (incident_id, code)
);

CREATE TABLE sensor_readings (
  id              bigserial PRIMARY KEY,
  sensor_id       bigint NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
  value           double precision NOT NULL,
  read_at         timestamptz NOT NULL,             -- when the instrument says it measured (a label)
  received_at     timestamptz NOT NULL DEFAULT now(),
  idempotency_key text NOT NULL,
  UNIQUE (sensor_id, idempotency_key)
);
CREATE INDEX sensor_readings_recent_idx ON sensor_readings (sensor_id, read_at DESC);
