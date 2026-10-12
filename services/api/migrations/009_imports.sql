-- 009 · spreadsheet imports (PRD §10, F-D3).
CREATE TABLE imports (
  id             bigserial PRIMARY KEY,
  incident_id    bigint NOT NULL REFERENCES incidents(id),
  district_id    bigint REFERENCES districts(id),
  file_name      text NOT NULL,
  file_sha256    text NOT NULL,
  file_kind      text NOT NULL CHECK (file_kind IN ('csv', 'xlsx')),
  encoding       text,
  uploaded_by    bigint REFERENCES users(id),
  headers        jsonb NOT NULL DEFAULT '[]',
  mapping        jsonb,                        -- header → field, as confirmed by a person
  proposed       jsonb,                        -- what the synonym list suggested
  preview        jsonb NOT NULL DEFAULT '[]',
  rows_total     integer NOT NULL DEFAULT 0,
  rows_done      integer NOT NULL DEFAULT 0,
  new_cases      integer NOT NULL DEFAULT 0,
  merged         integer NOT NULL DEFAULT 0,
  to_check       integer NOT NULL DEFAULT 0,
  dropped        integer NOT NULL DEFAULT 0,
  rules_read     integer NOT NULL DEFAULT 0,
  ai_asked       integer NOT NULL DEFAULT 0,
  phones_damaged integer NOT NULL DEFAULT 0,
  warnings       text[] NOT NULL DEFAULT '{}',
  status         text NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'mapped', 'running', 'done', 'failed')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  started_at     timestamptz,
  finished_at    timestamptz
);
