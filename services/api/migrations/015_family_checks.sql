-- 015 · the family's optional check (PRD F-S3): one answer per linked device per case. Silence is never stored.
CREATE TABLE family_checks (
  id          bigserial PRIMARY KEY,
  case_id     bigint NOT NULL REFERENCES cases(id),
  rescue_id   bigint REFERENCES rescues(id),
  device_hash text NOT NULL,
  on_site     boolean NOT NULL,                  -- the person who was there, or a relative far away
  answer      text NOT NULL CHECK (answer IN ('yes', 'no')),
  at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, device_hash)
);
