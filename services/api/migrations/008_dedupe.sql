-- 008 · duplicate handling (PRD §10, F-D1, F-D2).
CREATE TABLE merge_suggestions (
  id                bigserial PRIMARY KEY,
  incident_id       bigint NOT NULL REFERENCES incidents(id),
  case_id           bigint NOT NULL REFERENCES cases(id),        -- the newer case (made from the new report)
  candidate_case_id bigint NOT NULL REFERENCES cases(id),        -- the existing, older case
  score             numeric(4, 3) NOT NULL,
  strength          text NOT NULL CHECK (strength IN ('strong', 'weak', 'refused')),
  signals           jsonb NOT NULL,
  reasons           text[] NOT NULL DEFAULT '{}',
  conflicts         text[] NOT NULL DEFAULT '{}',
  status            text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'accepted', 'rejected', 'superseded')),
  decided_by        bigint REFERENCES users(id),
  decided_at        timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX merge_suggestions_open_idx ON merge_suggestions (incident_id) WHERE status = 'open';

CREATE TABLE merges (
  id               bigserial PRIMARY KEY,
  incident_id      bigint NOT NULL REFERENCES incidents(id),
  target_case_id   bigint NOT NULL REFERENCES cases(id),          -- the older, canonical case
  source_case_id   bigint REFERENCES cases(id),                   -- a case folded in (null when a report was attached directly)
  source_report_id bigint REFERENCES reports(id),
  score            numeric(4, 3),
  signals          jsonb NOT NULL DEFAULT '{}',
  reasons          text[] NOT NULL DEFAULT '{}',
  decided_by       text NOT NULL,                                 -- 'rule' or a user id
  decided_at       timestamptz NOT NULL DEFAULT now(),
  snapshot         jsonb NOT NULL,                                -- exact before-state, so undo restores it exactly
  undone_by        bigint REFERENCES users(id),
  undone_at        timestamptz,
  undo_reason      text
);

-- A pair a person said is NOT the same household (an undo, or a rejected suggestion): never suggested again.
CREATE TABLE merge_blocks (
  case_a     bigint NOT NULL REFERENCES cases(id),
  case_b     bigint NOT NULL REFERENCES cases(id),
  created_by bigint REFERENCES users(id),
  reason     text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (case_a, case_b),
  CHECK (case_a < case_b)
);
